"""Current time/date tool — avoids putting time in system prompt (which breaks caching).

Claude Code pattern: time is a tool, not system prompt content. The system prompt stays
static and cacheable, while the LLM calls this tool when it needs to know the time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tools.base import Tool, ToolResult


class GetCurrentTimeTool(Tool):
    name = "get_current_time"
    description = "Get the current date, time, and day of the week."
    parameters = {
        "type": "object",
        "properties": {},
    }

    def prompt(self) -> str:
        return """Tool: get_current_time
Returns the current date, time, and day of the week.

When to use:
- You need to know today's date for time-sensitive research
- User asks about "recent", "latest", "this week", "today"
- You need to set date filters for knowledge base searches

No parameters needed — just call it.
"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        now = datetime.now()
        return ToolResult(
            success=True,
            data=(
                f"Current date: {now.strftime('%A, %B %d, %Y')}\n"
                f"Current time: {now.strftime('%H:%M:%S %Z')}\n"
                f"ISO format: {now.isoformat()}"
            ),
            metadata={"iso": now.isoformat()},
        )
