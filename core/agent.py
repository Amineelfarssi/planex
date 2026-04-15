"""Agent — the single orchestrator for all paths.

Methods:
  plan()    — goal → structured task plan (STRATEGIC LLM)
  execute() — run planned tasks in parallel → synthesis
  turn()    — ReAct loop for follow-ups (yields typed events)
  ingest()  — add documents to KB
  status()  — KB stats + recent sessions
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from core.context import ContextManager
from core.executor import Executor
from core.knowledge import KnowledgeStore
from core.llm import LLMProvider, OpenAIProvider
from core.memory import MemoryManager
from core.models import RewrittenQuery
from core.planner import Planner
from core.state import PlanState, StateManager, Task
from tools.base import ToolRegistry


def _create_llm_provider() -> LLMProvider:
    """Pick LLM provider. Order:
    1. Explicit PLANEX_PROVIDER env var (bedrock | openai)
    2. If OPENAI_API_KEY is set → OpenAI
    3. If running on AWS (SageMaker / EC2) → Bedrock
    4. Fallback → OpenAI (will fail fast with a clear error if no key)
    """
    provider = os.environ.get("PLANEX_PROVIDER", "").lower()
    if provider == "bedrock":
        from core.llm_bedrock import BedrockAnthropicProvider
        return BedrockAnthropicProvider()
    if provider == "openai":
        return OpenAIProvider()

    # Auto-detect: API key present → OpenAI, AWS environment → Bedrock
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIProvider()
    if os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or os.environ.get("SAGEMAKER_APP_TYPE"):
        from core.llm_bedrock import BedrockAnthropicProvider
        return BedrockAnthropicProvider()

    return OpenAIProvider()


# ---------------------------------------------------------------------------
# Agent events — transport-agnostic (not SSE, not AG-UI)
# The SSE layer (react_loop.py) converts these to AG-UI format.
# ---------------------------------------------------------------------------

@dataclass
class AgentEvent:
    """A typed event from the agent. Transport-agnostic."""
    kind: str   # step_start, step_end, tool_start, tool_args, tool_end, tool_result,
                # text_delta, text_done, rewrite, state, run_start, run_end
    data: dict


MAX_REACT_TURNS = 6


class Agent:
    """Main Planex agent — orchestrates all paths."""

    def __init__(self) -> None:
        self.llm = _create_llm_provider()
        self.knowledge = KnowledgeStore(self.llm)
        self.memory = MemoryManager(self.llm)
        self.state = StateManager()

        self.tools = ToolRegistry()
        self.tools.auto_discover()

        for tool in self.tools.list_tools():
            if hasattr(tool, "set_store"):
                tool.set_store(self.knowledge)

        self.context = ContextManager(self.llm, self.memory)
        self.planner = Planner(self.llm, self.tools, self.knowledge, self.state)
        self.executor = Executor(self.llm, self.tools, self.knowledge, self.context, self.state)

    # ------------------------------------------------------------------
    # Plan → Execute path (initial research)
    # ------------------------------------------------------------------

    async def plan(self, goal: str) -> PlanState:
        import time as _time
        t0 = _time.time()
        self.memory.load_memory()
        print(f"[TIMING] load_memory: {_time.time() - t0:.2f}s")
        t1 = _time.time()
        await self.knowledge.scan_sources_dir()
        print(f"[TIMING] scan_sources_dir: {_time.time() - t1:.2f}s")
        return await self.planner.create_plan(goal)

    async def execute(
        self,
        plan: PlanState,
        on_task_update: Callable[[Task, str], None] | None = None,
    ) -> str:
        synthesis = await self.executor.execute_plan(plan, on_task_update)
        await self._post_session(plan, synthesis)
        return synthesis

    async def run(self, goal: str, on_task_update=None) -> tuple[PlanState, str]:
        plan = await self.plan(goal)
        synthesis = await self.execute(plan, on_task_update)
        return plan, synthesis

    async def research(self, goal: str) -> AsyncIterator[AgentEvent]:
        """Full research flow as an event stream: plan → execute → synthesize.

        Yields AgentEvents so the frontend can show live progress.
        """
        import time as _time
        from dataclasses import asdict

        run_id = str(uuid.uuid4())[:8]
        start_time = _time.time()

        yield AgentEvent("run_start", {"runId": run_id})

        # Step 1: Planning
        yield AgentEvent("step_start", {"stepId": "planning", "name": "Creating research plan"})
        plan = await self.plan(goal)
        yield AgentEvent("state", {
            "plan_id": plan.plan_id,
            "plan_title": plan.plan_title,
            "goal": plan.goal,
            "status": plan.status,
            "tasks": [
                {"id": t.id, "title": t.title, "status": t.status,
                 "tool_hint": t.tool_hint, "depends_on": t.depends_on}
                for t in plan.tasks
            ],
        })
        yield AgentEvent("step_end", {"stepId": "planning"})

        # Step 2: Executing tasks
        yield AgentEvent("step_start", {"stepId": "executing", "name": "Executing research tasks"})

        groups = self.state.get_pending_groups(plan)
        for group in groups:
            for task in group:
                yield AgentEvent("tool_start", {
                    "toolCallId": task.id,
                    "toolName": task.tool_hint or "agent",
                })
                yield AgentEvent("tool_args", {
                    "toolCallId": task.id,
                    "args": {"task": task.title, "description": task.description},
                })

            # Execute the group
            if len(group) == 1:
                await self.executor._execute_task(plan, group[0])
            else:
                await asyncio.gather(
                    *[self.executor._execute_task(plan, t) for t in group]
                )

            for task in group:
                yield AgentEvent("tool_end", {"toolCallId": task.id})
                yield AgentEvent("tool_result", {
                    "toolCallId": task.id,
                    "content": task.result_summary[:300] if task.result_summary else "No result",
                })
                # Update task status in state snapshot
                yield AgentEvent("state", {
                    "plan_id": plan.plan_id,
                    "tasks": [
                        {"id": t.id, "title": t.title, "status": t.status,
                         "tool_hint": t.tool_hint, "depends_on": t.depends_on,
                         "result_summary": (t.result_summary or "")[:200]}
                        for t in plan.tasks
                    ],
                })

        yield AgentEvent("step_end", {"stepId": "executing"})

        # Step 3: Synthesis (streaming)
        yield AgentEvent("step_start", {"stepId": "synthesis", "name": "Synthesizing findings"})
        synthesis = await self.executor._synthesize(plan)
        self.state.set_synthesis(plan, synthesis)
        self.state.set_status(plan, "completed")

        # Auto-ingest synthesis
        if synthesis and len(synthesis) > 100:
            try:
                await self.knowledge.ingest_text(
                    text=synthesis, source=f"session:{plan.plan_id}",
                    source_type="session_synthesis",
                    ingested_by=f"session:{plan.plan_id}",
                    title=plan.plan_title,
                )
            except Exception:
                pass

        # Stream synthesis as text deltas
        for i in range(0, len(synthesis), 40):
            yield AgentEvent("text_delta", {"delta": synthesis[i:i+40]})
        yield AgentEvent("text_done", {"full": synthesis})

        yield AgentEvent("step_end", {"stepId": "synthesis"})

        # Post-processing
        await self._post_session(plan, synthesis)

        elapsed = _time.time() - start_time
        yield AgentEvent("state", {
            "status": "completed",
            "plan_id": plan.plan_id,
            "duration": round(elapsed, 1),
        })
        yield AgentEvent("run_end", {"runId": run_id})

    # ------------------------------------------------------------------
    # ReAct turn (follow-ups) — yields AgentEvents
    # ------------------------------------------------------------------

    async def turn(
        self,
        user_message: str,
        chat_history: list[dict],
        session_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run a follow-up turn through the ReAct loop.

        Yields AgentEvents (transport-agnostic).
        Handles: query rewriting, context assembly, tool calls, streaming,
        AND post-processing (memory extraction, KB ingestion, session save).
        """
        run_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Load session
        session_context = ""
        plan = None
        if session_id:
            plan = self.state.load(session_id)
            if plan:
                session_context = (plan.synthesis or "")[:3000]

        yield AgentEvent("run_start", {"runId": run_id})

        # Assemble context — attention handles pronoun resolution natively
        messages = self._build_context(user_message, chat_history, session_context)

        # Step 3: ReAct loop
        yield AgentEvent("step_start", {"stepId": "react", "name": "Thinking"})

        tools_schema = self.tools.get_tools_schema()
        full_response = ""
        used_tools = False

        for turn_num in range(MAX_REACT_TURNS):
            resp = await self.llm.chat(
                messages=messages,
                tools=tools_schema if tools_schema else None,
                tier="smart",
            )

            if resp.tool_calls:
                used_tools = True
                for tc in resp.tool_calls:
                    tool_call_id = tc.id or str(uuid.uuid4())[:8]

                    yield AgentEvent("tool_start", {"toolCallId": tool_call_id, "toolName": tc.name})
                    yield AgentEvent("tool_args", {"toolCallId": tool_call_id, "args": tc.arguments})

                    # Execute
                    tool = self.tools.get(tc.name)
                    if tool:
                        try:
                            result = await tool.execute(**tc.arguments)
                            tool_output = result.data[:2000]
                        except Exception as e:
                            tool_output = f"Tool error: {e}"
                    else:
                        tool_output = f"Unknown tool: {tc.name}"

                    yield AgentEvent("tool_end", {"toolCallId": tool_call_id})
                    yield AgentEvent("tool_result", {"toolCallId": tool_call_id, "content": tool_output[:500]})

                    # Append in provider-native format
                    messages.append(self.llm.format_tool_call(tool_call_id, tc.name, tc.arguments))
                    messages.append(self.llm.format_tool_result(tool_call_id, tool_output))

                continue  # loop — LLM sees tool results

            full_response = resp.content or ""
            break

        yield AgentEvent("step_end", {"stepId": "react"})

        # Step 4: Stream response
        if used_tools and full_response:
            # Already have response from chat() — chunk it
            for i in range(0, len(full_response), 30):
                yield AgentEvent("text_delta", {"delta": full_response[i:i+30]})
        else:
            # True streaming — no tools were called
            full_response = ""
            async for token in self.llm.chat_stream(messages=messages, tier="smart"):
                full_response += token
                yield AgentEvent("text_delta", {"delta": token})

        yield AgentEvent("text_done", {"full": full_response})

        # Step 5: Post-processing (same as execute() path)
        if plan:
            self.state.add_chat_message(plan, "user", user_message)
            self.state.add_chat_message(plan, "assistant", full_response)

            # Extract learnings from substantial responses
            if len(full_response) > 500:
                try:
                    extracts = await self.memory._extract_learnings(
                        plan.goal, full_response
                    )
                    if extracts:
                        plan.memory_extracts.extend(extracts)
                        self.state.save(plan)
                except Exception:
                    pass

                # Auto-ingest into KB if it's substantial research
                if used_tools and len(full_response) > 300:
                    try:
                        await self.knowledge.ingest_text(
                            text=full_response,
                            source=f"followup:{plan.plan_id}",
                            source_type="session_synthesis",
                            ingested_by=f"session:{plan.plan_id}",
                            title=f"Follow-up: {user_message[:50]}",
                        )
                    except Exception:
                        pass

        elapsed = time.time() - start_time
        total_tokens = sum(u.total for u in self.llm.total_usage.values()) if self.llm.total_usage else 0

        yield AgentEvent("state", {"status": "done", "tokens": total_tokens, "duration": round(elapsed, 1)})
        yield AgentEvent("run_end", {"runId": run_id})

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    async def _rewrite_query(self, message: str, history: list[dict], session_context: str) -> str:
        if not history and not session_context:
            return message
        if len(message.split()) > 25:
            return message

        # Only call the LLM rewriter when there are ambiguous pronouns to resolve
        pronouns = {"it", "them", "they", "this", "that", "these", "those", "its", "their", "he", "she"}
        words = set(message.lower().split())
        if not words & pronouns:
            return message

        prompt = (
            "Rewrite this message into a standalone question. "
            "Resolve ALL pronouns using the research context.\n"
            "Return the original UNCHANGED if already clear.\n\n"
            + (f"RESEARCH CONTEXT:\n{session_context[:800]}\n\n" if session_context else "")
            + (f"CONVERSATION:\n" + "\n".join(f"{m['role']}: {m['content'][:100]}" for m in history[-4:]) + "\n\n" if history else "")
            + f"MESSAGE: {message}"
        )
        try:
            result: RewrittenQuery = await self.llm.chat_parse(
                messages=[{"role": "user", "content": prompt}],
                response_model=RewrittenQuery,
                tier="fast",
            )
            return result.query if result.changed else message
        except Exception:
            return message

    def _build_context(self, query: str, chat_history: list[dict], session_context: str) -> list[dict]:
        memory_md = self.memory.load_memory()

        system_parts = [
            "You are Planex, an AI research assistant with a persistent knowledge base.",
            "Use markdown formatting. Be thorough but concise. Cite sources.",
            "SCOPE: Research only — search, read, analyze, compare, synthesize.",
            "You have access to tools. Use them when you need current information.",
            "If you can answer from the provided context, do so without calling tools.",
            "OFF-TOPIC: If the user's question is clearly unrelated to the current research session, "
            "gently point out that this seems unrelated to the current research and suggest starting "
            "a new session for a fresh topic. If they insist or ask again, answer it but prefix with "
            "a brief note: '*(This is outside the current research scope.)*'",
        ]
        if memory_md.strip():
            system_parts.append(f"\n[Long-term memory]\n{memory_md[:600]}")
        if session_context:
            system_parts.append(f"\n[Current research]\n{session_context}")

        system = "\n".join(system_parts)
        messages = [{"role": "system", "content": system}]
        for m in chat_history[-6:]:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": query})
        return messages

    async def _post_session(self, plan: PlanState, synthesis: str) -> None:
        """Post-processing after plan execution — memory + KB."""
        completed_tasks = [{"title": t.title, "status": t.status} for t in plan.tasks]
        output_files = [t.result_summary for t in plan.tasks if t.tool_hint == "write_file" and t.status == "completed"]

        extracts = await self.memory.save_session_summary(
            plan.goal, plan.plan_id, completed_tasks, output_files, synthesis
        )
        self.state.set_memory_extracts(plan, extracts)

    # ------------------------------------------------------------------
    # Ingest + Status
    # ------------------------------------------------------------------

    async def ingest(self, path: str) -> tuple[int, int]:
        p = Path(path).expanduser().resolve()
        if p.is_file():
            chunks = await self.knowledge.ingest_file(str(p), "local_file", "user_upload")
            return 1 if chunks > 0 else 0, chunks
        elif p.is_dir():
            return await self.knowledge.ingest_directory(str(p), "user_upload")
        return 0, 0

    def status(self) -> dict:
        return {
            "knowledge_base": self.knowledge.get_stats(),
            "recent_sessions": self.state.list_sessions(),
            "memory": self.memory.load_memory()[:200],
        }
