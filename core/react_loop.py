"""SSE transport layer — maps AgentEvents to AG-UI formatted SSE strings.

The agent logic lives in Agent.turn(). This module only handles
the AG-UI event protocol formatting for HTTP streaming.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from ag_ui.core import EventType

from core.agent import Agent, AgentEvent

# Map AgentEvent kinds to AG-UI event types
_EVENT_MAP = {
    "run_start": EventType.RUN_STARTED,
    "run_end": EventType.RUN_FINISHED,
    "step_start": EventType.STEP_STARTED,
    "step_end": EventType.STEP_FINISHED,
    "tool_start": EventType.TOOL_CALL_START,
    "tool_args": EventType.TOOL_CALL_ARGS,
    "tool_end": EventType.TOOL_CALL_END,
    "tool_result": EventType.TOOL_CALL_RESULT,
    "text_delta": EventType.TEXT_MESSAGE_CONTENT,
    "state": EventType.STATE_SNAPSHOT,
}


def _to_sse(event: AgentEvent) -> str:
    """Convert an AgentEvent to an AG-UI SSE data line."""
    ag_type = _EVENT_MAP.get(event.kind, event.kind)
    data = {**event.data, "type": ag_type}
    return f"data: {json.dumps(data)}\n\n"


def _event_sse(event_type: str, data: dict) -> str:
    """Direct SSE formatting (used by tests)."""
    data["type"] = event_type
    return f"data: {json.dumps(data)}\n\n"


async def run_turn(
    agent: Agent,
    user_message: str,
    chat_history: list[dict],
    session_id: str | None = None,
) -> AsyncIterator[str]:
    """Stream AG-UI SSE events from an agent turn.

    Thin wrapper: Agent.turn() yields AgentEvents → this converts to SSE.
    Also handles TEXT_MESSAGE_START/END framing.
    """
    msg_id = None
    text_started = False

    async for event in agent.turn(user_message, chat_history, session_id):

        if event.kind == "text_delta" and not text_started:
            # Emit TEXT_MESSAGE_START before first delta
            msg_id = event.data.get("messageId", "msg")
            yield _event_sse(EventType.TEXT_MESSAGE_START, {"messageId": msg_id, "role": "assistant"})
            text_started = True

        if event.kind == "text_done":
            # Emit TEXT_MESSAGE_END after all deltas
            if text_started:
                yield _event_sse(EventType.TEXT_MESSAGE_END, {"messageId": msg_id or "msg"})
            continue  # don't emit text_done as an AG-UI event

        if event.kind == "rewrite":
            # Custom event — not in AG-UI spec
            yield _event_sse("custom", {"name": "rewrite", "value": event.data.get("query", "")})
            continue

        if event.kind == "tool_args":
            # Convert args dict to JSON string for AG-UI format
            args = event.data.get("args", {})
            yield _event_sse(EventType.TOOL_CALL_ARGS, {
                "toolCallId": event.data.get("toolCallId", ""),
                "args": json.dumps(args) if isinstance(args, dict) else str(args),
            })
            continue

        if event.kind == "state":
            yield _event_sse(EventType.STATE_SNAPSHOT, {"snapshot": event.data})
            continue

        # Default: map directly
        yield _to_sse(event)
