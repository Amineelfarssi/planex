"""Shared fixtures — isolated environment, no real API calls, 30s timeout."""

import asyncio
import os
import signal
import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Environment isolation (borrowed from Hermes agent)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_planex_home(tmp_path, monkeypatch):
    """Redirect ~/.planex to temp dir — tests never write to real home."""
    fake_home = tmp_path / "planex_test"
    fake_home.mkdir()
    (fake_home / "sessions").mkdir()
    (fake_home / "memory").mkdir()
    (fake_home / "memory" / "sessions").mkdir()
    (fake_home / "sources").mkdir()
    (fake_home / "outputs").mkdir()

    # Write a minimal MEMORY.md
    (fake_home / "memory" / "MEMORY.md").write_text("# Planex Memory\n\n## User Preferences\n")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
    monkeypatch.setenv("PLANEX_FAST_MODEL", "gpt-5-nano-2025-08-07")
    monkeypatch.setenv("PLANEX_SMART_MODEL", "gpt-5-mini")
    monkeypatch.setenv("PLANEX_STRATEGIC_MODEL", "gpt-5.1")

    # Patch home dir for memory/state modules
    import core.memory as mem_mod
    import core.state as state_mod
    monkeypatch.setattr(mem_mod, "MEMORY_DIR", fake_home / "memory")
    monkeypatch.setattr(mem_mod, "SESSIONS_DIR", fake_home / "memory" / "sessions")
    monkeypatch.setattr(state_mod, "SESSIONS_DIR", fake_home / "sessions")


@pytest.fixture(autouse=True)
def _enforce_test_timeout():
    """30-second timeout per test to prevent hangs (Unix only)."""
    if sys.platform == "win32":
        yield
        return

    def _handler(signum, frame):
        raise TimeoutError("Test exceeded 30s timeout")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(30)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old)


# ---------------------------------------------------------------------------
# Mock LLM provider (no real API calls)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_llm():
    """Mock LLMProvider that returns predictable responses."""
    from core.llm import LLMResponse, TokenUsage

    llm = MagicMock()
    llm.total_usage = {}

    async def fake_chat(messages, tools=None, response_format=None, tier="smart"):
        return LLMResponse(
            content='{"intent": "chat", "reason": "test"}',
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
        )

    async def fake_chat_parse(messages, response_model, tier="smart"):
        # Return a default instance of whatever model is requested
        return response_model.model_validate(response_model.model_json_schema().get("examples", [{}])[0] if response_model.model_json_schema().get("examples") else _default_for_model(response_model))

    async def fake_embed(texts):
        return [[0.1] * 1536 for _ in texts]

    async def fake_stream(messages, tools=None, tier="smart"):
        for word in ["Hello", " ", "world"]:
            yield word

    llm.chat = AsyncMock(side_effect=fake_chat)
    llm.chat_parse = AsyncMock(side_effect=fake_chat_parse)
    llm.embed = AsyncMock(side_effect=fake_embed)
    llm.chat_stream = fake_stream

    return llm


def _default_for_model(model_cls):
    """Create a minimal valid instance of a Pydantic model."""
    from core.models import (
        IntentClassification, RewrittenQuery, ResearchPlan, PlanTask,
        DocumentMetadata, MemoryExtraction, QueryVariants, KBChunkMetadata,
    )

    defaults = {
        IntentClassification: {"intent": "chat", "reason": "test"},
        RewrittenQuery: {"query": "test query", "changed": False},
        ResearchPlan: {"plan_title": "Test Plan", "tasks": [{"id": "t1", "title": "Test task", "description": "Do something", "tool_hint": "web_search"}]},
        DocumentMetadata: {"title": "Test Doc", "tags": ["test"], "content_type": "notes"},
        MemoryExtraction: {"learnings": ["test fact"], "should_save": True},
        QueryVariants: {"variants": ["query 1", "query 2", "query 3"]},
    }
    return defaults.get(model_cls, {})
