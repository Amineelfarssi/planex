"""Web search tool using OpenAI's native web search (Responses API).

No separate API key needed — uses the existing OpenAI key.
Returns results with inline citations and source URLs.
"""

from __future__ import annotations

import os
from typing import Any

from openai import AsyncOpenAI

from tools.base import Tool, ToolResult


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web for current information. Returns text with cited sources."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query — be specific and descriptive",
            },
        },
        "required": ["query"],
    }

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def prompt(self) -> str:
        return """Tool: web_search
Search the web for current information using OpenAI's built-in web search.
Returns text with inline citations and source URLs.

When to use:
- User asks about topics NOT covered by the knowledge base
- Need current/recent information (news, trends, latest research)
- Need to find authoritative sources on a specific topic
- Knowledge base search returned no relevant results

When NOT to use:
- Question is about documents the user has ingested (use knowledge_search)
- Simple factual questions you can answer from training data
- The knowledge base already has relevant content on this topic

Parameters:
- query: Be specific. Include the topic, timeframe, and what aspect you're researching.
  Good: "GEPA architecture transformer model 2024 2025"
  Bad: "AI trends"
"""

    def is_available(self) -> tuple[bool, str]:
        if os.getenv("OPENAI_API_KEY"):
            return True, "OpenAI web search available"
        return False, "OPENAI_API_KEY not set"

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs["query"]

        try:
            model = os.getenv("PLANEX_SMART_MODEL", "gpt-5-mini")
            response = await self._client.responses.create(
                model=model,
                input=query,
                tools=[{"type": "web_search"}],
            )

            text = response.output_text or ""
            if not text:
                return ToolResult(success=False, data="Web search returned no results.", metadata={})

            # Extract citations from output items
            urls = []
            try:
                for item in response.output:
                    if hasattr(item, 'content'):
                        for block in item.content:
                            if hasattr(block, 'annotations'):
                                for ann in block.annotations:
                                    if hasattr(ann, 'url'):
                                        urls.append(ann.url)
            except Exception:
                pass

            return ToolResult(
                success=True,
                data=text,
                metadata={"urls": list(set(urls)), "source": "openai_web_search"},
            )
        except Exception as e:
            return ToolResult(success=False, data=f"Web search failed: {e}", metadata={})
