"""Three-layer memory system: short-term (context), long-term (markdown), knowledge (LanceDB).

This module handles the long-term layer:
  - MEMORY.md: always-on brain, loaded every session
  - Daily session notes: today + yesterday auto-loaded, older searchable
  - Memory flush: save important context before compaction
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.llm import LLMProvider

MEMORY_DIR = Path.home() / ".planex" / "memory"
SESSIONS_DIR = MEMORY_DIR / "sessions"

FLUSH_PROMPT = """Review the following conversation context and extract important information that should be remembered for future sessions.

Focus on:
- User preferences or corrections
- Key decisions made
- Important findings or conclusions
- Recurring topics or patterns

Return a concise bullet-point list of facts to remember. If nothing important, return "Nothing to save."

Context:
{context}"""

SESSION_SUMMARY_PROMPT = """Summarize this research session in 3-5 bullet points.
Include: the goal, key findings, outputs created, and sources used.

Session data:
{session_data}"""


class MemoryManager:

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def memory_path(self) -> Path:
        return MEMORY_DIR / "MEMORY.md"

    def _daily_note_path(self, date: datetime | None = None) -> Path:
        d = date or datetime.utcnow()
        return SESSIONS_DIR / f"{d.strftime('%Y-%m-%d')}.md"

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_memory(self) -> str:
        """Load MEMORY.md content. Creates if not exists."""
        if not self.memory_path.exists():
            self.memory_path.write_text(
                "# Planex Memory\n\n## User Preferences\n\n## Key Decisions\n\n## Recurring Context\n",
                encoding="utf-8",
            )
        return self.memory_path.read_text(encoding="utf-8")

    def load_daily_notes(self) -> str:
        """Load today's and yesterday's session notes."""
        today = datetime.utcnow()
        yesterday = today - timedelta(days=1)

        notes = []
        for d in [yesterday, today]:
            path = self._daily_note_path(d)
            if path.exists():
                content = path.read_text(encoding="utf-8")
                if content.strip():
                    notes.append(content)

        return "\n\n---\n\n".join(notes) if notes else ""

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_memory(self, content: str) -> None:
        """Overwrite MEMORY.md with new content."""
        self.memory_path.write_text(content, encoding="utf-8")

    def append_memory(self, text: str) -> None:
        """Append a line/section to MEMORY.md."""
        current = self.load_memory()
        self.save_memory(current.rstrip() + "\n" + text + "\n")

    def append_daily_note(self, text: str) -> None:
        """Append text to today's session note."""
        path = self._daily_note_path()
        if not path.exists():
            path.write_text(f"# {datetime.utcnow().strftime('%Y-%m-%d')}\n\n", encoding="utf-8")
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n\n")

    # ------------------------------------------------------------------
    # Memory flush (before compaction)
    # ------------------------------------------------------------------

    async def flush(self, context_summary: str) -> str:
        """Extract important facts from context and save to long-term memory.

        Called before context compaction to prevent information loss.
        Returns what was saved.
        """
        resp = await self._llm.chat(
            messages=[{"role": "user", "content": FLUSH_PROMPT.format(context=context_summary[:3000])}],
            tier="fast",
        )
        extracted = resp.content or ""

        if extracted.strip() and "nothing to save" not in extracted.lower():
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            self.append_memory(f"\n## Extracted {timestamp}\n{extracted}")
            return extracted
        return ""

    async def save_session_summary(
        self, goal: str, plan_id: str, task_results: list[dict], output_files: list[str], synthesis: str = "",
    ) -> list[str]:
        """Write session summary to daily notes + extract learnings to MEMORY.md.

        Returns list of extracted memory items.
        """
        session_data = f"Goal: {goal}\nSession ID: {plan_id}\n"
        for tr in task_results:
            session_data += f"- Task: {tr.get('title', '?')}, Status: {tr.get('status', '?')}\n"
        if output_files:
            session_data += f"Outputs: {', '.join(output_files)}\n"

        resp = await self._llm.chat(
            messages=[{"role": "user", "content": SESSION_SUMMARY_PROMPT.format(session_data=session_data)}],
            tier="fast",
        )
        summary = resp.content or session_data

        now = datetime.utcnow().strftime("%H:%M")
        self.append_daily_note(f"## Session {plan_id} at {now}\n{summary}")

        # Extract key learnings to MEMORY.md
        extracts = await self._extract_learnings(goal, synthesis)
        return extracts

    async def _extract_learnings(self, goal: str, synthesis: str) -> list[str]:
        """Extract key facts/learnings from a research session into MEMORY.md."""
        if not synthesis:
            return []

        from core.models import MemoryExtraction

        try:
            result: MemoryExtraction = await self._llm.chat_parse(
                messages=[{
                    "role": "user",
                    "content": (
                        "Extract 2-3 key facts worth remembering from this research.\n\n"
                        f"Goal: {goal}\n\nFindings:\n{synthesis[:2000]}"
                    ),
                }],
                response_model=MemoryExtraction,
                tier="fast",
            )

            if result.should_save and result.learnings:
                timestamp = datetime.utcnow().strftime("%Y-%m-%d")
                bullets = "\n".join(f"- {l}" for l in result.learnings)
                self.append_memory(f"\n### Learned {timestamp}\n{bullets}")
                return result.learnings
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------
    # Search older notes
    # ------------------------------------------------------------------

    def search_notes(self, query: str) -> list[str]:
        """Simple keyword search over all daily notes."""
        results = []
        query_lower = query.lower()
        for path in sorted(SESSIONS_DIR.glob("*.md"), reverse=True):
            content = path.read_text(encoding="utf-8")
            if query_lower in content.lower():
                results.append(f"**{path.stem}**\n{content[:500]}")
            if len(results) >= 5:
                break
        return results
