"""Test structured output models — the contracts all LLM calls depend on."""

import pytest
from pydantic import ValidationError
from core.models import (
    IntentClassification, RewrittenQuery, ResearchPlan, PlanTask,
    DocumentMetadata, MemoryExtraction, ClarificationRequest,
    ClarificationOption, QueryVariants, KBChunkMetadata, KBIngestResult,
)


class TestIntentClassification:
    def test_valid_intents(self):
        for intent in ("chat", "research", "kb_query"):
            result = IntentClassification(intent=intent, reason="test")
            assert result.intent == intent

    def test_requires_reason(self):
        with pytest.raises(ValidationError):
            IntentClassification(intent="chat")


class TestRewrittenQuery:
    def test_unchanged(self):
        r = RewrittenQuery(query="hello", changed=False)
        assert not r.changed

    def test_changed(self):
        r = RewrittenQuery(query="Compare GEPA to transformers", changed=True)
        assert r.changed
        assert "GEPA" in r.query


class TestResearchPlan:
    def test_valid_plan(self):
        plan = ResearchPlan(
            plan_title="Test Research",
            tasks=[
                PlanTask(id="t1", title="Search web", description="Search", tool_hint="web_search"),
                PlanTask(id="t2", title="Read article", description="Read", tool_hint="read_url", depends_on=["t1"]),
            ],
        )
        assert len(plan.tasks) == 2
        assert plan.tasks[1].depends_on == ["t1"]

    def test_empty_tasks_allowed(self):
        plan = ResearchPlan(plan_title="Empty", tasks=[])
        assert len(plan.tasks) == 0

    def test_task_defaults(self):
        task = PlanTask(id="t1", title="Test", description="Desc", tool_hint="web_search")
        assert task.depends_on == []


class TestKBChunkMetadata:
    def test_full_metadata(self):
        meta = KBChunkMetadata(
            id="abc123", chunk_index=0, source="/test.pdf",
            source_type="local_file", doc_title="Test Doc",
            ingested_by="user_upload", created_at="2026-04-04T00:00:00",
            file_hash="sha256hash", token_count=512,
        )
        assert meta.source_type == "local_file"
        assert meta.language == "en"  # default
        assert meta.tags == []  # default

    def test_requires_hash(self):
        with pytest.raises(ValidationError):
            KBChunkMetadata(
                id="x", chunk_index=0, source="x", source_type="x",
                doc_title="x", ingested_by="x", created_at="x",
                token_count=0,
                # missing file_hash
            )

    def test_serialization_roundtrip(self):
        meta = KBChunkMetadata(
            id="test", chunk_index=0, source="/doc.md",
            source_type="session_synthesis", doc_title="Research",
            ingested_by="session:abc", created_at="2026-04-04",
            tags=["ai", "research"], content_type="synthesis",
            file_hash="abc123", token_count=256,
        )
        json_str = meta.model_dump_json()
        restored = KBChunkMetadata.model_validate_json(json_str)
        assert restored.tags == ["ai", "research"]
        assert restored.content_type == "synthesis"


class TestClarificationRequest:
    def test_valid_request(self):
        req = ClarificationRequest(
            question="Which comparison?",
            options=[
                ClarificationOption(label="A vs B", description="Compare A to B", query="compare A to B"),
                ClarificationOption(label="A vs C", description="Compare A to C", query="compare A to C"),
            ],
        )
        assert len(req.options) == 2
        assert req.options[0].query == "compare A to B"


class TestDocumentMetadata:
    def test_valid(self):
        meta = DocumentMetadata(title="Test", tags=["ai"], content_type="research")
        assert meta.title == "Test"

    def test_defaults(self):
        meta = DocumentMetadata(title="X", tags=[], content_type="notes")
        assert meta.content_type == "notes"
