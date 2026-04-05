"""Planner — decomposes a high-level goal into a structured task plan.

Uses STRATEGIC tier (reasoning=high) with structured output (ResearchPlan).
Topic grounding, tool awareness, KB relevance — all via prompt engineering.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.knowledge import KnowledgeStore
from core.llm import LLMProvider
from core.models import ResearchPlan
from core.state import PlanState, StateManager
from tools.base import ToolRegistry


class TopicExtraction(BaseModel):
    """Core topic extracted from a user goal."""
    topic: str = Field(description="The specific subject/topic the user wants to research (2-5 words)")


PLANNER_SYSTEM = """You are a research planning assistant. Break down the user's goal into a focused list of executable tasks.

# Critical Rules
- Task titles MUST directly reference the user's SPECIFIC topic — never use generic titles
  GOOD: "Search web for GEPA transformer architecture papers"
  BAD: "Search for latest AI trends"
- Each task uses ONE tool (specified as tool_hint)
- Only use knowledge_search if KB topics are RELEVANT to the goal (see KB info below)
- If KB has no relevant content, skip knowledge_search — go straight to web_search
- Independent tasks should have empty depends_on so they run in parallel
- Keep plans focused: 3-5 tasks. Never more than 7.
- Task IDs: t1, t2, t3, etc.
- Each task description must specify EXACTLY what to search for, read, or write
- tool_hint must be one of the available tools listed below

# Tool Selection
{tools_with_status}

# Knowledge Base
{kb_status}"""


class Planner:

    def __init__(
        self,
        llm: LLMProvider,
        tool_registry: ToolRegistry,
        knowledge_store: KnowledgeStore,
        state_manager: StateManager,
    ) -> None:
        self._llm = llm
        self._tools = tool_registry
        self._kb = knowledge_store
        self._state = state_manager

    def _get_tools_with_status(self) -> str:
        lines = []
        for tool in self._tools.list_tools():
            available = True
            note = ""
            if hasattr(tool, 'is_available'):
                available, note = tool.is_available()
            status = "AVAILABLE" if available else f"UNAVAILABLE ({note})"
            lines.append(f"- {tool.name}: {tool.description} [{status}]")
        return "\n".join(lines) if lines else "No tools available."

    def _get_valid_tool_names(self) -> set[str]:
        return {t.name for t in self._tools.list_tools()}

    async def _extract_topic(self, goal: str) -> str:
        """Use FAST LLM to extract the core topic — no hacky string splitting."""
        try:
            result: TopicExtraction = await self._llm.chat_parse(
                messages=[{"role": "user", "content": f"Extract the core research topic from this goal:\n\n{goal}"}],
                response_model=TopicExtraction,
                tier="fast",
            )
            return result.topic
        except Exception:
            return goal[:60]

    def _validate_plan(self, tasks: list[dict]) -> list[dict]:
        """Validate and fix the plan before creating state."""
        valid_tools = self._get_valid_tool_names()
        seen_ids: set[str] = set()

        for i, task in enumerate(tasks):
            # Ensure unique IDs
            if task.get("id") in seen_ids or not task.get("id"):
                task["id"] = f"t{i+1}"
            seen_ids.add(task["id"])

            # Ensure required fields
            task.setdefault("title", "Untitled task")
            task.setdefault("description", task["title"])
            task.setdefault("depends_on", [])

            # Fix invalid tool hints
            if task.get("tool_hint") not in valid_tools:
                task["tool_hint"] = "web_search" if "web_search" in valid_tools else ""

            # Fix dependencies pointing to nonexistent tasks
            task["depends_on"] = [d for d in task["depends_on"] if d in seen_ids or d in {t.get("id") for t in tasks}]

        return tasks

    async def create_plan(self, goal: str) -> PlanState:
        """Generate a structured plan from a user goal."""
        kb_stats = self._kb.get_stats()

        if kb_stats['chunks'] > 0:
            tags = kb_stats.get('tags', [])
            kb_status = (
                f"Documents: {kb_stats['documents']}, Chunks: {kb_stats['chunks']}\n"
                f"Topics in KB: {', '.join(tags[:10]) if tags else 'unknown'}\n"
                "Only use knowledge_search if these topics are relevant to the user's goal."
            )
        else:
            kb_status = (
                "Knowledge base is EMPTY — no documents ingested.\n"
                "Do NOT create knowledge_search tasks. Use web_search instead."
            )

        # Extract topic via LLM (not hacky string splitting)
        topic = await self._extract_topic(goal)

        system = PLANNER_SYSTEM.format(
            tools_with_status=self._get_tools_with_status(),
            kb_status=kb_status,
        )

        try:
            plan: ResearchPlan = await self._llm.chat_parse(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Create a research plan for: {goal}\n\nThe core topic is: {topic}"},
                ],
                response_model=ResearchPlan,
                tier="strategic",
            )
            tasks = [t.model_dump() for t in plan.tasks]
            plan_title = plan.plan_title
        except Exception as e:
            # Fallback: single-task plan using first available tool
            fallback_tool = next(iter(self._get_valid_tool_names()), "web_search")
            tasks = [{"id": "t1", "title": f"Research: {topic}", "description": goal, "tool_hint": fallback_tool, "depends_on": []}]
            plan_title = f"Research: {topic}"

        # Validate: fix bad tool hints, duplicate IDs, broken deps
        tasks = self._validate_plan(tasks)

        return self._state.create_plan(goal, plan_title, tasks)
