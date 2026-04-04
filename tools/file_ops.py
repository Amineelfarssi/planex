"""Read and write local files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import tiktoken

from tools.base import Tool, ToolResult

_ENC = tiktoken.get_encoding("cl100k_base")
MAX_READ_TOKENS = 8000
OUTPUTS_DIR = Path.home() / ".planex" / "outputs"


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a local file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read",
            },
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"]).expanduser().resolve()
        if not path.exists():
            return ToolResult(success=False, data=f"File not found: {path}", metadata={})
        if not path.is_file():
            return ToolResult(success=False, data=f"Not a file: {path}", metadata={})

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tokens = _ENC.encode(text)
            if len(tokens) > MAX_READ_TOKENS:
                text = _ENC.decode(tokens[:MAX_READ_TOKENS]) + "\n\n[... truncated]"
            return ToolResult(
                success=True,
                data=text,
                metadata={"path": str(path), "token_count": min(len(tokens), MAX_READ_TOKENS)},
            )
        except Exception as e:
            return ToolResult(success=False, data=f"Failed to read file: {e}", metadata={})


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file in the outputs directory (~/.planex/outputs/)."
    parameters = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Name of the output file (e.g., 'summary.md')",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["filename", "content"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        filename = kwargs["filename"]
        content = kwargs["content"]

        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUTS_DIR / filename

        try:
            path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                data=f"Written to {path}",
                metadata={"path": str(path), "size": len(content)},
            )
        except Exception as e:
            return ToolResult(success=False, data=f"Failed to write file: {e}", metadata={})
