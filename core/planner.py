"""Planner — decomposes a high-level goal into a structured task plan.

Adapted from Claude Code's planning patterns:
- Tool availability awareness (knows which tools actually work)
- Topic-grounded task titles (never generic)
- KB relevance check before including knowledge_search tasks
"""

from __future__ import annotations

from core.knowledge import KnowledgeStore
from core.llm import LLMProvider
from core.models import ResearchPlan
from core.state import PlanState, StateManager
from tools.base import ToolRegistry

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

# Tool Selection
{tools_with_status}

# Knowledge Base
{kb_status}"""

PLANNER_PROMPT = """Create a research plan for this SPECIFIC goal:

"{goal}"

Important: The plan title and ALL task titles must reference "{topic}" specifically.

Return a JSON object:
{{
  "plan_title": "title referencing the specific topic",
  "tasks": [
    {{
      "id": "t1",
      "title": "specific action about the specific topic",
      "description": "detailed instructions — what exactly to search/read/write",
      "tool_hint": "tool_name",
      "depends_on": []
    }}
  ]
}}"""


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
        """Build tool descriptions with availability status."""
        lines = []
        for tool in self._tools.list_tools():
            available = True
            note = ""
            if hasattr(tool, 'is_available'):
                available, note = tool.is_available()
            status = "AVAILABLE" if available else f"UNAVAILABLE ({note})"
            lines.append(f"- {tool.name}: {tool.description} [{status}]")
        return "\n".join(lines) if lines else "No tools available."

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

        # Extract core topic from goal for grounding
        topic = goal.strip().rstrip("?.!").split("about")[-1].split("on")[-1].strip()
        if len(topic) > 60 or len(topic) < 3:
            topic = goal[:60]

        system = PLANNER_SYSTEM.format(
            tools_with_status=self._get_tools_with_status(),
            kb_status=kb_status,
        )

        try:
            plan: ResearchPlan = await self._llm.chat_parse(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": PLANNER_PROMPT.format(goal=goal, topic=topic)},
                ],
                response_model=ResearchPlan,
                tier="strategic",
            )
            tasks = [t.model_dump() for t in plan.tasks]
            plan_title = plan.plan_title
        except Exception:
            tasks = [{"id": "t1", "title": f"Web search: {goal[:60]}", "description": goal, "tool_hint": "web_search", "depends_on": []}]
            plan_title = f"Research: {goal[:50]}"

        return self._state.create_plan(goal, plan_title, tasks)
