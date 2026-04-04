"""Context assembly pipeline — where the three memory layers converge.

Assembles LLM context from:
  1. System prompt + tool descriptions
  2. MEMORY.md (long-term, always loaded)
  3. Today's session notes (long-term, auto-loaded)
  4. Current plan + task description
  5. Knowledge chunks (RAG retrieval per task)
  6. Recent task results (short-term)
  7. Compacted older results
"""

from __future__ import annotations

import tiktoken

from core.llm import LLMProvider
from core.memory import MemoryManager
from core.state import PlanState, Task

_ENC = tiktoken.get_encoding("cl100k_base")

SYSTEM_PROMPT = """You are Planex, an AI research assistant with a persistent knowledge base.

You help users tackle complex research goals by:
1. Breaking them into actionable tasks with specific tool calls
2. Executing each task using the right tool
3. Learning from results (auto-ingesting into knowledge base)
4. Synthesizing findings into well-structured markdown reports

Important rules:
- ALWAYS use tools when available — don't guess or make up information
- Task titles MUST reference the user's specific topic
- Only search the knowledge base if its topics are relevant to the goal
- If a tool fails, explain what happened and suggest alternatives
- Cite sources in your synthesis
- Use markdown formatting for all responses

Use the get_current_time tool if you need to know the current date or time.

{tool_descriptions}"""


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


class ContextManager:

    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryManager,
        token_budget: int = 100_000,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._token_budget = token_budget
        self._compacted_summary: str = ""
        self._task_results: list[dict] = []  # {task_id, title, summary}

    def add_task_result(self, task_id: str, title: str, summary: str) -> None:
        self._task_results.append({"task_id": task_id, "title": title, "summary": summary})

    def assemble(
        self,
        plan: PlanState,
        current_task: Task | None,
        tool_descriptions: str,
        knowledge_context: str = "",
    ) -> list[dict]:
        """Build the message list for an LLM call."""
        messages: list[dict] = []

        # 1. System prompt
        system = SYSTEM_PROMPT.format(tool_descriptions=f"\nAvailable tools:\n{tool_descriptions}")
        messages.append({"role": "system", "content": system})

        # 2. MEMORY.md
        memory_content = self._memory.load_memory()
        if memory_content.strip():
            messages.append({"role": "system", "content": f"[Long-term memory]\n{memory_content}"})

        # 3. Today's daily notes
        daily = self._memory.load_daily_notes()
        if daily.strip():
            messages.append({"role": "system", "content": f"[Recent session notes]\n{daily[:1000]}"})

        # 4. Current plan
        plan_summary = f"Goal: {plan.goal}\nPlan: {plan.plan_title}\n"
        for t in plan.tasks:
            status_icon = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]", "failed": "[!]"}.get(t.status, "[ ]")
            plan_summary += f"  {status_icon} {t.id}: {t.title}\n"
        messages.append({"role": "user", "content": f"[Current plan]\n{plan_summary}"})

        # 5. Knowledge context (RAG retrieval)
        if knowledge_context:
            messages.append({"role": "system", "content": f"[Relevant knowledge]\n{knowledge_context[:3000]}"})

        # 6. Compacted older results
        if self._compacted_summary:
            messages.append({"role": "system", "content": f"[Previous findings]\n{self._compacted_summary}"})

        # 7. Recent task results (last 3)
        recent = self._task_results[-3:]
        for tr in recent:
            messages.append({
                "role": "assistant",
                "content": f"[Result: {tr['title']}]\n{tr['summary'][:1500]}",
            })

        # 8. Current task instruction
        if current_task:
            messages.append({
                "role": "user",
                "content": f"Now execute this task: {current_task.title}\n{current_task.description}\n\nUse the appropriate tool to accomplish this.",
            })

        return messages

    def should_compact(self) -> bool:
        """Check if we need to compact context."""
        total = sum(count_tokens(m["content"]) for m in self._task_results_as_messages())
        return total > self._token_budget * 0.7

    def _task_results_as_messages(self) -> list[dict]:
        return [{"content": f"{tr['title']}: {tr['summary']}"} for tr in self._task_results]

    async def compact(self) -> None:
        """Summarize older task results and flush memory."""
        if len(self._task_results) <= 3:
            return

        # Flush important context to long-term memory
        context_text = "\n".join(f"- {tr['title']}: {tr['summary'][:200]}" for tr in self._task_results)
        await self._memory.flush(context_text)

        # Summarize older results
        old_results = self._task_results[:-3]
        summary_text = "\n".join(f"- {tr['title']}: {tr['summary'][:150]}" for tr in old_results)

        resp = await self._llm.chat(
            messages=[{
                "role": "user",
                "content": f"Summarize these research findings in one concise paragraph:\n{summary_text}",
            }],
            tier="fast",
        )
        self._compacted_summary = resp.content or summary_text[:500]
        self._task_results = self._task_results[-3:]  # keep only recent
