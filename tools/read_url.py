"""Fetch and extract readable content from a URL."""

from __future__ import annotations

from typing import Any

import httpx
import tiktoken

from tools.base import Tool, ToolResult

_ENC = tiktoken.get_encoding("cl100k_base")
MAX_TOKENS = 4000


class ReadUrlTool(Tool):
    name = "read_url"
    description = "Fetch a web page and extract its main text content. Use after web_search to read full articles."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch and extract content from",
            },
        },
        "required": ["url"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = kwargs["url"]
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(url, headers={"User-Agent": "Planex/1.0 Research Assistant"})
                resp.raise_for_status()
                html = resp.text

            import trafilatura

            text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
            if not text:
                return ToolResult(success=False, data="Could not extract content from URL.", metadata={"url": url})

            # Truncate to token limit
            tokens = _ENC.encode(text)
            if len(tokens) > MAX_TOKENS:
                text = _ENC.decode(tokens[:MAX_TOKENS]) + "\n\n[... truncated]"

            title = trafilatura.extract_metadata(html)
            title_str = title.title if title and title.title else url

            return ToolResult(
                success=True,
                data=f"# {title_str}\n\n{text}",
                metadata={"url": url, "title": title_str, "token_count": min(len(tokens), MAX_TOKENS)},
            )
        except Exception as e:
            return ToolResult(success=False, data=f"Failed to fetch URL: {e}", metadata={"url": url})
