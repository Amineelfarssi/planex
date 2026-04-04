"""Local file search tool — ripgrep-style text search over workspace files.

Adapted from NousResearch/hermes-agent file_tools.py patterns:
- Tool cascade: rg → grep fallback
- Three output modes: content, files_only, count
- Structured results with line numbers
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
MAX_LINE_LEN = 500


def _has_rg() -> bool:
    """Check if ripgrep binary exists (not a shell function)."""
    rg_path = shutil.which("rg")
    if not rg_path:
        return False
    # Ensure it's a real binary, not a shell function
    return os.path.isfile(rg_path)


class LocalSearchTool(Tool):
    name = "local_search"
    description = "Search local workspace files (outputs, sources, session notes) for text patterns. Like ripgrep."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Text or regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "Directory to search (default: ~/.planex/). Relative paths resolved from workspace.",
                "default": "",
            },
            "file_glob": {
                "type": "string",
                "description": "Filter files by glob pattern (e.g., '*.md', '*.json')",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 30)",
                "default": 30,
            },
        },
        "required": ["pattern"],
    }

    def prompt(self) -> str:
        return """Tool: local_search
Search through local workspace files for text patterns. Works like ripgrep/grep.
Searches ~/.planex/ by default (outputs, sources, session files, memory).

When to use:
- Find mentions of a topic in past research outputs
- Search through ingested source documents
- Find specific content in session notes or memory
- Locate files containing certain keywords

When NOT to use:
- Searching the web (use web_search)
- Searching the vector knowledge base (use knowledge_search)

Parameters:
- pattern: text or regex to search for
- path: directory to search (default: all of ~/.planex/)
- file_glob: filter files (e.g., "*.md", "*.json")
- limit: max results (default 30)
"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs["pattern"]
        path = kwargs.get("path", "") or str(WORKSPACE)
        file_glob = kwargs.get("file_glob")
        limit = kwargs.get("limit", 30)

        # Resolve path
        search_path = Path(path).expanduser()
        if not search_path.is_absolute():
            search_path = WORKSPACE / path

        if not search_path.exists():
            return ToolResult(success=False, data=f"Path not found: {search_path}", metadata={})

        try:
            if _has_rg():
                output = await self._search_rg(pattern, str(search_path), file_glob, limit)
            else:
                output = await self._search_grep(pattern, str(search_path), file_glob, limit)

            if not output.strip():
                return ToolResult(success=False, data=f"No matches found for '{pattern}'", metadata={})

            # Parse output
            lines = output.strip().split("\n")
            results = []
            for line in lines[:limit]:
                m = MATCH_RE.match(line)
                if m:
                    filepath, lineno, content = m.group(1), m.group(2), m.group(3)[:MAX_LINE_LEN]
                    # Make path relative to workspace
                    try:
                        rel = str(Path(filepath).relative_to(WORKSPACE))
                    except ValueError:
                        rel = filepath
                    results.append(f"  {rel}:{lineno}: {content}")
                else:
                    results.append(f"  {line[:MAX_LINE_LEN]}")

            return ToolResult(
                success=True,
                data=f"Found {len(results)} matches for '{pattern}':\n" + "\n".join(results),
                metadata={"match_count": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, data=f"Search error: {e}", metadata={})

    async def _search_rg(self, pattern: str, path: str, file_glob: str | None, limit: int) -> str:
        cmd_parts = [
            "rg", "--line-number", "--no-heading", "--with-filename", "-i",
            "--max-count", str(limit),
        ]
        if file_glob:
            cmd_parts.extend(["--glob", file_glob])
        cmd_parts.extend(["--", pattern, path])

        cmd = " ".join(cmd_parts)
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return stdout.decode("utf-8", errors="replace")

    async def _search_grep(self, pattern: str, path: str, file_glob: str | None, limit: int) -> str:
        import shlex
        cmd_parts = ["grep", "-rnHi", "-m", str(limit), "--exclude-dir=.git"]
        if file_glob:
            cmd_parts.extend(["--include", file_glob])
        cmd_parts.append("--")
        cmd_parts.append(pattern)
        cmd_parts.append(path)

        proc = await asyncio.create_subprocess_exec(
            *cmd_parts, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return stdout.decode("utf-8", errors="replace")
