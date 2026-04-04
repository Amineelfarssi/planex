"""RAG retrieval over the persistent knowledge base."""

from __future__ import annotations

from typing import Any

from tools.base import Tool, ToolResult


class KnowledgeSearchTool(Tool):
    name = "knowledge_search"
    description = (
        "Search the local knowledge base for information from previously ingested documents "
        "and past research. Supports filtering by source type, date range, and topic tags."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "source_type": {
                "type": "string",
                "description": "Filter by source type: 'local_file', 'web_page', or None for all",
                "enum": ["local_file", "web_page", "web_search", "agent_output"],
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default 10)",
                "default": 10,
            },
        },
        "required": ["query"],
    }

    def __init__(self, knowledge_store: Any = None) -> None:
        self._store = knowledge_store

    def set_store(self, store: Any) -> None:
        self._store = store

    async def execute(self, **kwargs: Any) -> ToolResult:
        if self._store is None:
            return ToolResult(success=False, data="Knowledge base not initialized.", metadata={})

        query = kwargs["query"]
        top_k = kwargs.get("top_k", 10)
        source_type = kwargs.get("source_type")

        try:
            results = await self._store.search(
                query=query,
                top_k=top_k,
                source_type=source_type,
            )
            if not results:
                return ToolResult(success=False, data="No relevant documents found in knowledge base.", metadata={})

            lines = []
            sources = set()
            for chunk in results:
                source_label = chunk.get("doc_title", chunk.get("source", "unknown"))
                lines.append(f"**[{source_label}]** (type: {chunk.get('source_type', '?')})\n{chunk['text']}\n")
                sources.add(source_label)

            return ToolResult(
                success=True,
                data="\n---\n".join(lines),
                metadata={"sources": list(sources), "chunk_count": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, data=f"Knowledge search failed: {e}", metadata={})
