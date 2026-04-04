"""Test AG-UI event format — ensure ReAct loop emits valid events."""

import pytest
from ag_ui.core import EventType


class TestAGUIEventTypes:
    """Verify all event types we use exist in the protocol."""

    @pytest.mark.parametrize("event_type", [
        EventType.RUN_STARTED,
        EventType.RUN_FINISHED,
        EventType.STEP_STARTED,
        EventType.STEP_FINISHED,
        EventType.TOOL_CALL_START,
        EventType.TOOL_CALL_ARGS,
        EventType.TOOL_CALL_END,
        EventType.TOOL_CALL_RESULT,
        EventType.TEXT_MESSAGE_START,
        EventType.TEXT_MESSAGE_CONTENT,
        EventType.TEXT_MESSAGE_END,
        EventType.STATE_SNAPSHOT,
    ])
    def test_event_type_exists(self, event_type):
        assert event_type.value is not None
        assert isinstance(event_type.value, str)


class TestEventSSEFormat:
    def test_event_sse_format(self):
        from core.react_loop import _event_sse
        result = _event_sse(EventType.RUN_STARTED, {"runId": "test123"})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        import json
        data = json.loads(result[6:].strip())
        assert data["type"] == EventType.RUN_STARTED
        assert data["runId"] == "test123"

    def test_tool_call_event(self):
        from core.react_loop import _event_sse
        result = _event_sse(EventType.TOOL_CALL_START, {
            "toolCallId": "tc1",
            "toolCallName": "web_search",
        })
        import json
        data = json.loads(result[6:].strip())
        assert data["toolCallName"] == "web_search"

    def test_text_message_event(self):
        from core.react_loop import _event_sse
        result = _event_sse(EventType.TEXT_MESSAGE_CONTENT, {
            "messageId": "msg1",
            "delta": "Hello world",
        })
        import json
        data = json.loads(result[6:].strip())
        assert data["delta"] == "Hello world"
