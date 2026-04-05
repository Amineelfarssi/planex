"""Agent — the main orchestrator wiring plan → execute → learn → synthesize."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from core.context import ContextManager
from core.executor import Executor
from core.knowledge import KnowledgeStore
from core.llm import OpenAIProvider
from core.memory import MemoryManager
from core.planner import Planner
from core.state import PlanState, StateManager, Task
from tools.base import ToolRegistry
from tools.ingest import IngestDocumentsTool
from tools.knowledge_search import KnowledgeSearchTool


class Agent:
    """Main Planex agent — orchestrates research sessions."""

    def __init__(self) -> None:
        # Core components
        self.llm = OpenAIProvider()
        self.knowledge = KnowledgeStore(self.llm)
        self.memory = MemoryManager(self.llm)
        self.state = StateManager()

        # Tool registry with wired knowledge store
        self.tools = ToolRegistry()
        self.tools.auto_discover()

        # Wire knowledge store into knowledge-dependent tools
        for tool in self.tools.list_tools():
            if hasattr(tool, "set_store"):
                tool.set_store(self.knowledge)

        # Context manager
        self.context = ContextManager(self.llm, self.memory)

        # Planner + Executor
        self.planner = Planner(self.llm, self.tools, self.knowledge, self.state)
        self.executor = Executor(self.llm, self.tools, self.knowledge, self.context, self.state)

    async def plan(self, goal: str) -> PlanState:
        """Create a research plan from a goal."""
        # Load memory for context
        self.memory.load_memory()
        self.memory.load_daily_notes()

        # Scan sources directory for new docs
        new_files, new_chunks = await self.knowledge.scan_sources_dir()

        # Create plan
        plan = await self.planner.create_plan(goal)
        return plan

    async def execute(
        self,
        plan: PlanState,
        on_task_update: Callable[[Task, str], None] | None = None,
    ) -> str:
        """Execute a plan and return the synthesis."""
        synthesis = await self.executor.execute_plan(plan, on_task_update)

        # Save session summary to daily notes + extract learnings to MEMORY.md
        completed_tasks = [
            {"title": t.title, "status": t.status}
            for t in plan.tasks
        ]
        output_files = [
            t.result_summary
            for t in plan.tasks
            if t.tool_hint == "write_file" and t.status == "completed"
        ]
        extracts = await self.memory.save_session_summary(
            plan.goal, plan.plan_id, completed_tasks, output_files, synthesis
        )
        self.state.set_memory_extracts(plan, extracts)
        return synthesis

    async def run(
        self,
        goal: str,
        on_task_update: Callable[[Task, str], None] | None = None,
        auto_confirm: bool = False,
    ) -> tuple[PlanState, str]:
        """Full pipeline: plan → (confirm) → execute → synthesize."""
        plan = await self.plan(goal)
        synthesis = await self.execute(plan, on_task_update)
        return plan, synthesis

    async def ingest(self, path: str) -> tuple[int, int]:
        """Ingest files from a path into the knowledge base."""
        p = Path(path).expanduser().resolve()
        if p.is_file():
            chunks = await self.knowledge.ingest_file(str(p), "local_file", "user_upload")
            return 1 if chunks > 0 else 0, chunks
        elif p.is_dir():
            return await self.knowledge.ingest_directory(str(p), "user_upload")
        return 0, 0

    def status(self) -> dict:
        """Return KB stats and recent sessions."""
        return {
            "knowledge_base": self.knowledge.get_stats(),
            "recent_sessions": self.state.list_sessions(),
            "memory": self.memory.load_memory()[:200],
        }
