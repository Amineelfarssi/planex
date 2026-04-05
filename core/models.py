"""Structured output models for all LLM calls.

Every model here is passed to client.responses.parse(text_format=Model)
or used as a data schema for LanceDB. OpenAI guarantees the response
matches the schema — zero parsing failures.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Intent Router
# ---------------------------------------------------------------------------

class IntentClassification(BaseModel):
    """Classify a user message into an intent."""
    intent: str = Field(description="One of: chat, research, kb_query")
    reason: str = Field(description="One sentence explaining why this intent was chosen")


# ---------------------------------------------------------------------------
# Query Rewriter
# ---------------------------------------------------------------------------

class RewrittenQuery(BaseModel):
    """A standalone, fully-formed query with all references resolved."""
    query: str = Field(description="The rewritten query with all pronouns and references resolved")
    changed: bool = Field(description="True if the query was modified from the original")


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class PlanTask(BaseModel):
    """A single task in a research plan."""
    id: str = Field(description="Task ID like t1, t2, t3")
    title: str = Field(description="What this task does — must reference the specific research topic")
    description: str = Field(description="Detailed instructions for the executor")
    tool_hint: str = Field(description="Which tool to use: web_search, read_url, knowledge_search, write_file")
    depends_on: list[str] = Field(default_factory=list, description="Task IDs this depends on")


class ResearchPlan(BaseModel):
    """A structured research plan decomposed from a user goal."""
    plan_title: str = Field(description="Short descriptive title referencing the specific topic")
    tasks: list[PlanTask] = Field(description="3-7 tasks in execution order")


# ---------------------------------------------------------------------------
# Metadata Extraction (for document ingestion)
# ---------------------------------------------------------------------------

class DocumentMetadata(BaseModel):
    """Metadata extracted from a document's first chunk."""
    title: str = Field(description="Document title or short description")
    tags: list[str] = Field(description="2-5 topic tags")
    content_type: str = Field(description="One of: research, report, notes, raw_data, article")


# ---------------------------------------------------------------------------
# Memory Extraction
# ---------------------------------------------------------------------------

class MemoryExtraction(BaseModel):
    """Key learnings extracted from a research session."""
    learnings: list[str] = Field(description="2-3 key facts worth remembering for future sessions")
    should_save: bool = Field(description="True if there are notable learnings. False if trivial.")


# ---------------------------------------------------------------------------
# Clarification (AskUser)
# ---------------------------------------------------------------------------

class ClarificationOption(BaseModel):
    """One option in a clarification request."""
    label: str = Field(description="Short title for this option")
    description: str = Field(description="What this option means")
    query: str = Field(description="The refined query if user picks this option")


class ClarificationRequest(BaseModel):
    """Generated when a query is ambiguous and needs user input."""
    question: str = Field(description="The question to ask the user")
    options: list[ClarificationOption] = Field(description="3-4 specific options")


# ---------------------------------------------------------------------------
# Query Variants (for RAG Fusion)
# ---------------------------------------------------------------------------

class QueryVariants(BaseModel):
    """Multiple search queries for RAG Fusion retrieval."""
    variants: list[str] = Field(description="3-4 search query variants approaching the topic from different angles")


# ---------------------------------------------------------------------------
# Knowledge Base — structured metadata
# ---------------------------------------------------------------------------

class KBChunkMetadata(BaseModel):
    """Metadata for a single chunk in the knowledge base.

    Every chunk in LanceDB carries this metadata. Enables filtering
    by source, date, session, content type, and provenance.
    """
    # Identity
    id: str = Field(description="Deterministic hash of source + chunk_index")
    chunk_index: int = Field(description="Position within the source document")

    # Source tracking
    source: str = Field(description="File path, URL, or session ID")
    source_type: str = Field(description="local_file | web_page | session_synthesis | agent_output")
    doc_title: str = Field(description="Document or page title")

    # Provenance
    ingested_by: str = Field(description="user_upload | auto_watch | session:<plan_id>")
    created_at: str = Field(description="ISO datetime when ingested into KB")
    source_date: str = Field(default="", description="Publication/modification date if detectable")

    # Classification (LLM-extracted)
    tags: list[str] = Field(default_factory=list, description="Topic tags extracted by LLM")
    content_type: str = Field(default="notes", description="research | report | notes | raw_data | article | synthesis")
    language: str = Field(default="en", description="Detected language")

    # Quality signals
    file_hash: str = Field(description="SHA-256 of source content for deduplication")
    token_count: int = Field(description="Token count of this chunk")


class KBStats(BaseModel):
    """Knowledge base statistics."""
    total_chunks: int = Field(default=0)
    total_sources: int = Field(default=0)
    source_types: dict[str, int] = Field(default_factory=dict, description="Count per source_type")
    top_tags: list[str] = Field(default_factory=list, description="Most frequent tags")
    sessions_contributing: int = Field(default=0, description="Number of sessions that contributed chunks")


class KBIngestResult(BaseModel):
    """Result of ingesting a file or text into the KB."""
    filename: str = Field(description="Name of the ingested file")
    chunks_created: int = Field(description="Number of chunks created")
    doc_title: str = Field(default="", description="Extracted document title")
    tags: list[str] = Field(default_factory=list, description="Extracted topic tags")
    content_type: str = Field(default="notes")
    already_exists: bool = Field(default=False, description="True if file was already in KB (dedup)")
