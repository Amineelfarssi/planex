"""Plan state management, persistence, and structured logging."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SESSIONS_DIR = Path.home() / ".planex" / "sessions"


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    tool_hint: str = ""
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | in_progress | completed | failed
    result_summary: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclass
class LogEntry:
    timestamp: str
    event_type: str  # plan_created | task_started | tool_call | task_completed | task_failed | synthesis
    task_id: str = ""
    tool_name: str = ""
    input_summary: str = ""
    output_summary: str = ""
    tokens_used: int = 0
    duration_ms: int = 0


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: str = ""


@dataclass
class PlanState:
    plan_id: str
    goal: str
    plan_title: str
    tasks: list[Task]
    status: str = "planning"  # planning | executing | completed | failed
    created_at: str = ""
    synthesis: str = ""  # final synthesized report (markdown)
    chat_history: list[ChatMessage] = field(default_factory=list)
    memory_extracts: list[str] = field(default_factory=list)  # key learnings saved to MEMORY.md
    logs: list[LogEntry] = field(default_factory=list)


class StateManager:

    def __init__(self) -> None:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def create_plan(self, goal: str, plan_title: str, tasks: list[dict]) -> PlanState:
        plan = PlanState(
            plan_id=str(uuid.uuid4())[:8],
            goal=goal,
            plan_title=plan_title,
            tasks=[Task(**t) for t in tasks],
            status="planning",
            created_at=datetime.utcnow().isoformat(),
        )
        self.add_log(plan, LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event_type="plan_created",
            output_summary=f"Plan '{plan_title}' with {len(tasks)} tasks",
        ))
        return plan

    def update_task(self, plan: PlanState, task_id: str, status: str, result_summary: str = "") -> None:
        for task in plan.tasks:
            if task.id == task_id:
                task.status = status
                if status == "in_progress":
                    task.started_at = datetime.utcnow().isoformat()
                elif status in ("completed", "failed"):
                    task.completed_at = datetime.utcnow().isoformat()
                if result_summary:
                    task.result_summary = result_summary
                break

    def add_log(self, plan: PlanState, entry: LogEntry) -> None:
        plan.logs.append(entry)

    def get_task(self, plan: PlanState, task_id: str) -> Task | None:
        for t in plan.tasks:
            if t.id == task_id:
                return t
        return None

    def get_pending_groups(self, plan: PlanState) -> list[list[Task]]:
        """Group pending tasks by dependency level for parallel execution."""
        completed_ids = {t.id for t in plan.tasks if t.status == "completed"}
        groups: list[list[Task]] = []

        remaining = [t for t in plan.tasks if t.status == "pending"]
        while remaining:
            # Find tasks whose dependencies are all completed
            ready = [t for t in remaining if all(d in completed_ids for d in t.depends_on)]
            if not ready:
                # Remaining tasks have unmet deps — force sequential
                groups.append(remaining)
                break
            groups.append(ready)
            completed_ids.update(t.id for t in ready)
            remaining = [t for t in remaining if t not in ready]

        return groups

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _path(self, plan_id: str) -> Path:
        return SESSIONS_DIR / f"{plan_id}.json"

    def save(self, plan: PlanState) -> None:
        data = asdict(plan)
        self._path(plan.plan_id).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, plan_id: str) -> PlanState | None:
        path = self._path(plan_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tasks"] = [Task(**t) for t in data["tasks"]]
        data["logs"] = [LogEntry(**l) for l in data.get("logs", [])]
        data["chat_history"] = [ChatMessage(**m) for m in data.get("chat_history", [])]
        data.setdefault("memory_extracts", [])
        data.setdefault("synthesis", "")
        return PlanState(**data)

    def add_chat_message(self, plan: PlanState, role: str, content: str) -> None:
        plan.chat_history.append(ChatMessage(
            role=role, content=content,
            timestamp=datetime.utcnow().isoformat(),
        ))
        self.save(plan)

    def list_sessions(self, limit: int = 10) -> list[dict]:
        """List recent sessions with basic info."""
        sessions = []
        for path in sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "plan_id": data["plan_id"],
                    "goal": data["goal"][:80],
                    "status": data["status"],
                    "created_at": data["created_at"],
                    "task_count": len(data["tasks"]),
                })
            except Exception:
                continue
        return sessions
