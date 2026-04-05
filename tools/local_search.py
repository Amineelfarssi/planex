"""Local file search tool — shells out to grep (or rg if available).

Adapted from NousResearch/hermes-agent file_tools.py:
- grep is the default (available everywhere)
- rg used if the binary exists (faster for large dirs)
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import Any

from tools.base import Tool, ToolResult

WORKSPACE = Path.home() / ".planex"
MATCH_RE = re.compile(r'^(.*?):(\d+):(.*)$')


def _find_rg() -> str | None:
    """Find real rg binary (not shell functions)."""
    path = shutil.which("rg")
    if path and os.path.isfile(path):
        return path
    return None


class LocalSearchTool(Tool):
    name = "local_search"
    description = "Search local workspace files for text patterns using grep/ripgrep."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Text or regex pattern to search for"},
            "path": {"type": "string", "description": "Directory to search (default: ~/.planex/)"},
            "file_glob": {"type": "string", "description": "Filter files (e.g. '*.md')"},
            "limit": {"type": "integer", "description": "Max results (default 30)"},
        },
        "required": ["pattern"],
        "additionalProperties": False,
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs["pattern"]
        path = kwargs.get("path") or str(WORKSPACE)
        file_glob = kwargs.get("file_glob")
        limit = kwargs.get("limit") or 30

        search_path = Path(path).expanduser()
        if not search_path.is_absolute():
            search_path = WORKSPACE / path
        if not search_path.exists():
            return ToolResult(success=False, data=f"Path not found: {search_path}", metadata={})

        rg = _find_rg()
        if rg:
            cmd = [rg, "--line-number", "--no-heading", "--with-filename", "-i",
                   "--max-count", str(limit)]
            if file_glob:
                cmd.extend(["--glob", file_glob])
            cmd.extend(["--", pattern, str(search_path)])
        else:
            cmd = ["/usr/bin/grep", "-rnHi", "-m", str(limit),
                   "--exclude-dir=.git", "--exclude-dir=__pycache__",
                   "--exclude-dir=node_modules", "--exclude-dir=.venv",
                   "--exclude-dir=knowledge.lance"]
            if file_glob:
                cmd.extend(["--include", file_glob])
            cmd.extend(["--", pattern, str(search_path)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode("utf-8", errors="replace")
        except Exception as e:
            return ToolResult(success=False, data=f"Search error: {e}", metadata={})

        if not output.strip():
            return ToolResult(success=False, data=f"No matches found for '{pattern}'", metadata={})

        lines = output.strip().split("\n")[:limit]
        results = []
        for line in lines:
            m = MATCH_RE.match(line)
            if m:
                fp, ln, content = m.group(1), m.group(2), m.group(3)[:500]
                try:
                    rel = str(Path(fp).relative_to(WORKSPACE))
                except ValueError:
                    rel = fp
                results.append(f"  {rel}:{ln}: {content}")
            else:
                results.append(f"  {line[:500]}")

        return ToolResult(
            success=True,
            data=f"Found {len(results)} matches for '{pattern}':\n" + "\n".join(results),
            metadata={"match_count": len(results)},
        )
