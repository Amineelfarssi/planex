"""Document ingestion tool — adds files/directories to the knowledge base."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base import Tool, ToolResult


class IngestDocumentsTool(Tool):
    name = "ingest_documents"
    description = "Add local files or directories to the knowledge base for future retrieval."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to a file or directory to ingest",
            },
        },
        "required": ["path"],
    }

    def __init__(self, knowledge_store: Any = None) -> None:
        self._store = knowledge_store

    def set_store(self, store: Any) -> None:
        self._store = store

    async def execute(self, **kwargs: Any) -> ToolResult:
        if self._store is None:
            return ToolResult(success=False, data="Knowledge base not initialized.", metadata={})

        path = Path(kwargs["path"]).expanduser().resolve()
        if not path.exists():
            return ToolResult(success=False, data=f"Path not found: {path}", metadata={})

        try:
            if path.is_file():
                count = await self._store.ingest_file(str(path), source_type="local_file", ingested_by="user_upload")
                return ToolResult(
                    success=True,
                    data=f"Ingested 1 file ({count} chunks) into knowledge base.",
                    metadata={"files": 1, "chunks": count},
                )
            elif path.is_dir():
                total_files, total_chunks = await self._store.ingest_directory(str(path), ingested_by="user_upload")
                return ToolResult(
                    success=True,
                    data=f"Ingested {total_files} files ({total_chunks} chunks) into knowledge base.",
                    metadata={"files": total_files, "chunks": total_chunks},
                )
            else:
                return ToolResult(success=False, data=f"Unsupported path type: {path}", metadata={})
        except Exception as e:
            return ToolResult(success=False, data=f"Ingestion failed: {e}", metadata={})
