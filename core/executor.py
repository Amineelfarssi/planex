"""Executor — runs plan tasks with parallel execution and auto-learning."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Callable

from core.context import ContextManager
from core.knowledge import KnowledgeStore
from core.llm import LLMProvider
from core.state import LogEntry, PlanState, StateManager, Task
from tools.base import ToolRegistry, ToolResult

TASK_SYSTEM = """You are executing a specific research task. Use the provided tool to accomplish it.
Call exactly ONE tool with appropriate arguments. Be precise with your tool arguments."""

SUMMARIZE_PROMPT = """Summarize this tool result concisely (2-3 sentences). Preserve key facts, data points, and source references.

Tool: {tool_name}
Result:
{result}"""

SYNTHESIS_PROMPT = """You are a research assistant synthesizing findings from multiple sources.

Based on the following task results and knowledge, create a comprehensive, well-structured answer to the user's research goal.

Goal: {goal}

Findings:
{findings}

Knowledge context:
{knowledge}

Instructions:
- Structure your response with clear sections/headers
- Cite sources where applicable
- Be thorough but concise
- Highlight key insights and conclusions"""


class Executor:

    def __init__(
        self,
        llm: LLMProvider,
        tool_registry: ToolRegistry,
        knowledge_store: KnowledgeStore,
        context_manager: ContextManager,
        state_manager: StateManager,
    ) -> None:
        self._llm = llm
        self._tools = tool_registry
        self._kb = knowledge_store
        self._ctx = context_manager
        self._state = state_manager

    async def execute_plan(
        self,
        plan: PlanState,
        on_task_update: Callable[[Task, str], None] | None = None,
    ) -> str:
        """Execute all tasks in dependency order, then synthesize."""
        self._state.set_status(plan, "executing")

        groups = self._state.get_pending_groups(plan)

        for group in groups:
            if len(group) == 1:
                await self._execute_task(plan, group[0], on_task_update)
            else:
                # Parallel execution
                await asyncio.gather(
                    *[self._execute_task(plan, task, on_task_update) for task in group]
                )

            # Check compaction after each group
            if self._ctx.should_compact():
                await self._ctx.compact()

            self._state.save(plan)

        # Synthesize final answer
        synthesis = await self._synthesize(plan)
        self._state.set_synthesis(plan, synthesis)
        self._state.set_status(plan, "completed")

        # Auto-ingest synthesis into KB (grows the knowledge base silently)
        if synthesis and len(synthesis) > 100:
            try:
                await self._kb.ingest_text(
                    text=synthesis,
                    source=f"session:{plan.plan_id}",
                    source_type="session_synthesis",
                    ingested_by=f"session:{plan.plan_id}",
                    title=plan.plan_title,
                    tags=[],
                )
            except Exception:
                pass  # non-critical

        return synthesis

    async def _execute_task(
        self,
        plan: PlanState,
        task: Task,
        on_task_update: Callable[[Task, str], None] | None = None,
    ) -> None:
        """Execute a single task: LLM decides tool call → run tool → summarize."""
        self._state.update_task(plan, task.id, "in_progress")
        if on_task_update:
            on_task_update(task, "in_progress")

        start_time = time.time()

        try:
            # Build context for this task
            tool_descriptions = self._tools.get_tools_description()
            knowledge_context = ""
            if task.tool_hint != "knowledge_search":
                # Pre-fetch relevant knowledge for non-KB tasks
                try:
                    kb_results = await self._kb.search(task.title, top_k=3, use_rag_fusion=False)
                    if kb_results:
                        knowledge_context = "\n".join(r.get("text", "")[:300] for r in kb_results)
                except Exception:
                    pass

            messages = self._ctx.assemble(plan, task, tool_descriptions, knowledge_context)

            # LLM decides tool call
            tools_schema = self._tools.get_tools_schema()
            resp = await self._llm.chat(messages=messages, tools=tools_schema, tier="smart")

            if resp.tool_calls:
                # Execute ALL tool calls (not just the first)
                all_results: list[str] = []

                for tc in resp.tool_calls:
                    tool = self._tools.get(tc.name)
                    if tool is None:
                        all_results.append(f"[Unknown tool: {tc.name}]")
                        continue

                    result = await tool.execute(**tc.arguments)

                    # Log
                    self._state.add_log(plan, LogEntry(
                        timestamp=datetime.utcnow().isoformat(),
                        event_type="tool_call",
                        task_id=task.id,
                        tool_name=tc.name,
                        input_summary=json.dumps(tc.arguments)[:200],
                        output_summary=result.data[:200],
                        tokens_used=resp.usage.total,
                        duration_ms=int((time.time() - start_time) * 1000),
                    ))

                    if result.success:
                        all_results.append(result.data)

                        # Auto-ingest web content into KB
                        if tc.name in ("read_url", "web_search") and len(result.data) > 100:
                            try:
                                await self._kb.ingest_text(
                                    text=result.data,
                                    source=result.metadata.get("url", f"web:{tc.name}"),
                                    source_type="web_page",
                                    ingested_by=f"session:{plan.plan_id}",
                                    title=result.metadata.get("title", task.title[:50]),
                                )
                            except Exception:
                                pass
                    else:
                        all_results.append(f"[Failed: {result.data[:100]}]")

                if all_results:
                    combined = "\n\n".join(all_results)

                    # Only summarize if result is long (skip LLM call for short results)
                    if len(combined) > 500:
                        summary_resp = await self._llm.chat(
                            messages=[{"role": "user", "content": SUMMARIZE_PROMPT.format(
                                tool_name=resp.tool_calls[0].name, result=combined[:3000]
                            )}],
                            tier="fast",
                        )
                        summary = summary_resp.content or combined[:500]
                    else:
                        summary = combined

                    self._state.update_task(plan, task.id, "completed", summary)
                    self._ctx.add_task_result(task.id, task.title, summary)
                    if on_task_update:
                        on_task_update(task, "completed")
                else:
                    self._state.update_task(plan, task.id, "failed", "All tool calls failed")
                    if on_task_update:
                        on_task_update(task, "failed")
            else:
                # LLM didn't call a tool — use its text response as the result
                summary = resp.content or "No result"
                self._state.update_task(plan, task.id, "completed", summary[:500])
                self._ctx.add_task_result(task.id, task.title, summary[:500])
                if on_task_update:
                    on_task_update(task, "completed")

        except Exception as e:
            self._state.update_task(plan, task.id, "failed", f"Error: {str(e)[:200]}")
            self._state.add_log(plan, LogEntry(
                timestamp=datetime.utcnow().isoformat(),
                event_type="task_failed",
                task_id=task.id,
                output_summary=str(e)[:200],
            ))
            if on_task_update:
                on_task_update(task, "failed")

    async def _synthesize(self, plan: PlanState) -> str:
        """Synthesize all task results into a final answer."""
        # Filter out garbage results — only include tasks with ACTUAL findings
        NOISE_PHRASES = [
            "no relevant documents", "not find any", "no results found",
            "no additional information", "yielded no relevant", "could not find",
            "unavailable", "not configured",
        ]

        findings = "\n\n".join(
            f"### {t.title}\n{t.result_summary}"
            for t in plan.tasks
            if t.status == "completed"
            and t.result_summary
            and not any(noise in t.result_summary.lower() for noise in NOISE_PHRASES)
        )

        if not findings.strip():
            failed_tools = [t.tool_hint for t in plan.tasks if t.status == "failed"]
            return (
                f"## Could not find sufficient information\n\n"
                f"I was unable to find relevant information about **{plan.goal}**.\n\n"
                f"**What happened:**\n"
                + ("".join(f"- Task '{t.title}': {t.result_summary[:100]}\n" for t in plan.tasks if t.result_summary))
                + f"\n**Suggestions:**\n"
                f"- Try rephrasing your research goal with more specific terms\n"
                f"- Ingest relevant documents into the knowledge base first\n"
                f"- Check that web search is working (needs OpenAI API access)\n"
            )

        # Get relevant knowledge
        knowledge = ""
        try:
            kb_results = await self._kb.search(plan.goal, top_k=5, use_rag_fusion=False)
            knowledge = "\n".join(r.get("text", "")[:300] for r in kb_results)
        except Exception:
            pass

        messages = [{"role": "user", "content": SYNTHESIS_PROMPT.format(
            goal=plan.goal,
            findings=findings,
            knowledge=knowledge[:2000],
        )}]

        # Stream synthesis
        full_response = ""
        async for chunk in self._llm.chat_stream(messages=messages, tier="smart"):
            full_response += chunk

        self._state.add_log(plan, LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event_type="synthesis",
            output_summary=full_response[:200],
        ))

        return full_response
