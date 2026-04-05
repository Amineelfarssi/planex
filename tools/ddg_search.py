"""DuckDuckGo web search — free, no API key, returns structured URLs.

Use this for finding source URLs. Use web_search (OpenAI) for
deep answers with citations. They complement each other.
"""

from __future__ import annotations

from typing import Any

from tools.base import Tool, ToolResult


class DDGSearchTool(Tool):
    name = "ddg_search"
    description = "Search the web via DuckDuckGo. Returns titles, URLs, and snippets. Free, no API key needed."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results (default 5)",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def prompt(self) -> str:
        return """Tool: ddg_search
Search the web via DuckDuckGo. Returns structured results with titles, URLs, and snippets.
Free, no API key required.

When to use:
- Find source URLs for a topic
- Quick web search when you need links, not deep analysis
- Complement web_search (OpenAI) which gives deeper answers but less structured URLs

Parameters:
- query: search terms
- max_results: how many results (default 5)
"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs["query"]
        max_results = kwargs.get("max_results") or 5

        try:
            from ddgs import DDGS

            results = DDGS().text(query, max_results=max_results)

            if not results:
                return ToolResult(success=False, data="No results found.", metadata={})

            lines = []
            urls = []
            for r in results:
                title = r.get("title", "Untitled")
                url = r.get("href", "")
                snippet = r.get("body", "")[:200]
                lines.append(f"**{title}**\n  URL: {url}\n  {snippet}\n")
                urls.append(url)

            return ToolResult(
                success=True,
                data="\n".join(lines),
                metadata={"urls": urls, "results": results},
            )
        except Exception as e:
            return ToolResult(success=False, data=f"DuckDuckGo search failed: {e}", metadata={})
