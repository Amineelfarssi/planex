"""Unified ReAct loop with AG-UI event streaming.

Every user message — whether first research or follow-up — goes through
the same loop. The LLM gets tools and decides whether to use them.

Flow:
  1. Rewrite query (resolve references)
  2. Assemble context (memory + session + KB)
  3. ReAct loop: LLM call with tools → if tool_call → execute → observe → repeat
  4. Stream AG-UI events throughout
"""

from __future__ import annotations

import json
import uuid
import time
from datetime import datetime
from typing import AsyncIterator, Any

from ag_ui.core import EventType

from core.agent import Agent
from core.models import RewrittenQuery

MAX_REACT_TURNS = 6  # max tool calls per message


def _event_sse(event_type: str, data: dict) -> str:
    """Format an AG-UI event as an SSE data line."""
    data["type"] = event_type
    return f"data: {json.dumps(data)}\n\n"


async def run_turn(
    agent: Agent,
    user_message: str,
    chat_history: list[dict],
    session_id: str | None = None,
) -> AsyncIterator[str]:
    """Run a single user turn through the ReAct loop, yielding AG-UI SSE events."""

    run_id = str(uuid.uuid4())[:8]
    msg_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Load session context
    session_context = ""
    plan = None
    if session_id:
        plan = agent.state.load(session_id)
        if plan:
            session_context = (plan.synthesis or "")[:3000]

    yield _event_sse(EventType.RUN_STARTED, {"runId": run_id})

    # Step 1: Rewrite query
    yield _event_sse(EventType.STEP_STARTED, {"stepId": "rewrite", "name": "Interpreting query"})

    try:
        result: RewrittenQuery = await agent.llm.chat_parse(
            messages=[{
                "role": "user",
                "content": (
                    "Rewrite this message into a standalone question. "
                    "Resolve ALL pronouns using the research context.\n"
                    "Return the original if already clear.\n\n"
                    + (f"RESEARCH CONTEXT:\n{session_context[:800]}\n\n" if session_context else "")
                    + (f"CONVERSATION:\n" + "\n".join(f"{m['role']}: {m['content'][:100]}" for m in chat_history[-4:]) + "\n\n" if chat_history else "")
                    + f"MESSAGE: {user_message}"
                ),
            }],
            response_model=RewrittenQuery,
            tier="fast",
        )
        query = result.query if result.changed else user_message
    except Exception:
        query = user_message

    if query != user_message:
        yield _event_sse("custom", {"name": "rewrite", "value": query})

    yield _event_sse(EventType.STEP_FINISHED, {"stepId": "rewrite"})

    # Step 2: Assemble context
    memory_md = agent.memory.load_memory()

    system_parts = [
        "You are Planex, an AI research assistant with a persistent knowledge base.",
        "Use markdown formatting. Be thorough but concise. Cite sources.",
        "SCOPE: Research only — search, read, analyze, compare, synthesize.",
        "You have access to tools. Use them when you need current information or to search the knowledge base.",
        "If you can answer from the provided context, do so without calling tools.",
    ]
    if memory_md.strip():
        system_parts.append(f"\n[Long-term memory]\n{memory_md[:600]}")
    if session_context:
        system_parts.append(f"\n[Current research]\n{session_context}")

    # KB search for additional context
    try:
        kb_results = await agent.knowledge.search(query, top_k=3, use_rag_fusion=False)
        if kb_results:
            kb_text = "\n".join(f"[{r.get('doc_title', '?')}]: {r.get('text', '')[:300]}" for r in kb_results)
            system_parts.append(f"\n[Knowledge base]\n{kb_text}")
    except Exception:
        pass

    system = "\n".join(system_parts)

    # Build messages
    messages = [{"role": "system", "content": system}]
    # Include recent chat history
    for m in chat_history[-6:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": query})

    # Step 3: ReAct loop
    yield _event_sse(EventType.STEP_STARTED, {"stepId": "react", "name": "Thinking"})

    tools_schema = agent.tools.get_tools_schema()
    full_response = ""

    for turn in range(MAX_REACT_TURNS):
        resp = await agent.llm.chat(
            messages=messages,
            tools=tools_schema if tools_schema else None,
            tier="smart",
        )

        # If LLM called a tool
        if resp.tool_calls:
            for tc in resp.tool_calls:
                tool_call_id = tc.id or str(uuid.uuid4())[:8]

                yield _event_sse(EventType.TOOL_CALL_START, {
                    "toolCallId": tool_call_id,
                    "toolCallName": tc.name,
                })
                yield _event_sse(EventType.TOOL_CALL_ARGS, {
                    "toolCallId": tool_call_id,
                    "args": json.dumps(tc.arguments),
                })

                # Execute tool
                tool = agent.tools.get(tc.name)
                if tool:
                    try:
                        result = await tool.execute(**tc.arguments)
                        tool_output = result.data[:2000]
                    except Exception as e:
                        tool_output = f"Tool error: {e}"
                else:
                    tool_output = f"Unknown tool: {tc.name}"

                yield _event_sse(EventType.TOOL_CALL_END, {"toolCallId": tool_call_id})
                yield _event_sse(EventType.TOOL_CALL_RESULT, {
                    "toolCallId": tool_call_id,
                    "content": tool_output[:500],
                    "role": "tool",
                })

                # Add tool call + result in Responses API format
                messages.append({
                    "type": "function_call",
                    "call_id": tool_call_id,
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                })
                messages.append({
                    "type": "function_call_output",
                    "call_id": tool_call_id,
                    "output": tool_output,
                })

            # Continue loop — LLM will see tool results and decide next action
            continue

        # LLM responded with text (no tool call) — stream it
        full_response = resp.content or ""
        break

    yield _event_sse(EventType.STEP_FINISHED, {"stepId": "react"})

    # Step 4: Stream the final text response
    yield _event_sse(EventType.TEXT_MESSAGE_START, {"messageId": msg_id, "role": "assistant"})

    # Stream in chunks for perceived speed
    chunk_size = 20
    for i in range(0, len(full_response), chunk_size):
        chunk = full_response[i:i + chunk_size]
        yield _event_sse(EventType.TEXT_MESSAGE_CONTENT, {"messageId": msg_id, "delta": chunk})

    yield _event_sse(EventType.TEXT_MESSAGE_END, {"messageId": msg_id})

    # Step 5: Save to session + memory
    if plan:
        agent.state.add_chat_message(plan, "user", user_message)
        agent.state.add_chat_message(plan, "assistant", full_response)

    elapsed = time.time() - start_time
    total_tokens = sum(u.total for u in agent.llm.total_usage.values()) if agent.llm.total_usage else 0

    yield _event_sse(EventType.STATE_SNAPSHOT, {
        "snapshot": {"status": "done", "tokens": total_tokens, "duration": round(elapsed, 1)},
    })
    yield _event_sse(EventType.RUN_FINISHED, {"runId": run_id})
