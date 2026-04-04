# Planex — AI Research Assistant with Persistent Knowledge Base

An autonomous AI agent that breaks complex research goals into plans, executes them using real tools, and builds a persistent knowledge base that grows smarter over time.

**Built for:** Wolters Kluwer AI Engineering Take-Home
**No agent frameworks** (LangChain, CrewAI, etc.) — custom Python with asyncio, as required.

---

## What Makes Planex Different

| vs. Plain ChatGPT | Planex |
|-------------------|--------|
| Stateless | Persistent knowledge base + memory across sessions |
| No document ingestion | Upload files, paste URLs, paste text |
| Manual tool use | Autonomous plan → execute → learn loop |
| No source attribution | Every finding traced to source |

| vs. GPT-Researcher | Planex |
|---------------------|--------|
| Stateless report generator | Research companion with growing KB |
| Web-only | Local docs + web, cross-referenced |
| One-shot | Follow-up questions with full context |

---

## Quick Start

### Prerequisites
- Python 3.11+
- OpenAI API key
- Node.js 18+ (for frontend)

### Install

```bash
cd planex

# Python backend
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e ".[dashboard,dev]"

# Frontend
cd frontend && npm install && cd ..

# Configure
cp .env.example .env
# Edit .env with your OpenAI key
# Or run `planex` for interactive onboarding
```

### Run

```bash
# Desktop app (recommended — single command)
python desktop.py

# Web app (two terminals)
planex serve                    # Terminal 1: FastAPI on :8000
cd frontend && npm run dev      # Terminal 2: Vite on :3000

# CLI one-shot
planex run "research quantum computing" -y
planex ingest ./docs/
planex status
```

---

## Architecture

### Unified ReAct Loop with AG-UI Events

Every user message — whether first research or follow-up — goes through the same loop:

```
User message
    │
    ▼
Query Rewriter (FAST LLM, structured output)
  → resolves "them", "it", "this" using session context
    │
    ▼
ReAct Loop (SMART LLM + tools):
  1. LLM sees: context + tools → decides action
  2. If tool_call → execute tool → feed result → loop
  3. If text → stream response → done
  4. AG-UI events emitted throughout (SSE)
    │
    ▼
Response streamed to frontend
  + saved to session + auto-ingested into KB
```

**AG-UI events** ([ag-ui-protocol](https://github.com/ag-ui-protocol/ag-ui)):
- `RUN_STARTED/FINISHED` — lifecycle
- `STEP_STARTED/FINISHED` — rewriting, thinking
- `TOOL_CALL_START/ARGS/END/RESULT` — tool execution with arguments and results
- `TEXT_MESSAGE_START/CONTENT/END` — streaming response
- `STATE_SNAPSHOT` — final status

### Three-Tier LLM Strategy

| Tier | Default Model | Reasoning | Used for |
|------|---------------|-----------|----------|
| FAST | gpt-5-nano | medium (auto) | Summaries, rewriting, routing, metadata extraction |
| SMART | gpt-5-mini | medium (auto) | Tool dispatch, synthesis, follow-up chat |
| STRATEGIC | gpt-5.1 | **high** (explicit) | Planning, decomposition |

All LLM calls returning structured data use **Pydantic models** with `client.beta.chat.completions.parse()` — zero parsing failures.

### Structured Output Models (`core/models.py`)

| Model | Purpose |
|-------|---------|
| `IntentClassification` | Route messages (chat/research/kb_query) |
| `RewrittenQuery` | Resolve pronouns using session context |
| `ResearchPlan` / `PlanTask` | Plan decomposition |
| `DocumentMetadata` | Extracted from ingested docs |
| `MemoryExtraction` | Key learnings from sessions |
| `KBChunkMetadata` | Structured metadata for every KB chunk |
| `ClarificationRequest` | Disambiguation options (rendered as clickable cards) |
| `QueryVariants` | RAG Fusion multi-query generation |

### Tools

| Tool | Source | Notes |
|------|--------|-------|
| `web_search` | OpenAI Responses API | Native web search, no extra API key |
| `read_url` | httpx + trafilatura | Fetch + extract web pages |
| `knowledge_search` | LanceDB | Vector search over KB |
| `local_search` | grep/ripgrep | Text search over workspace files |
| `ingest_documents` | LanceDB | Add files to KB |
| `read_file` / `write_file` | filesystem | Local file operations |
| `get_current_time` | datetime | Time as tool (not in system prompt — preserves caching) |

Tools borrowed from [Claude Code](https://github.com/zackautocracy/claude-code) patterns: per-tool `prompt()` method, `is_available()` for planner awareness, auto-discovery via registry.

### Knowledge Base (Invisible Tool)

LanceDB embedded vector DB at `~/.planex/knowledge.lance/`. Not a UI feature — a tool the agent calls silently.

**Grows automatically:**
- Session syntheses auto-ingested after every research
- User uploads (files, URLs, pasted text)
- Web content from research

**Structured metadata** (`KBChunkMetadata`): source tracking, provenance, tags, content type, file hash for dedup.

### Memory System

Three layers (inspired by [OpenClaw](https://openclaw.ai)):
- **MEMORY.md** — long-term learnings, loaded every session (~600 tokens)
- **Session JSON** — full state per session (tasks, synthesis, chat history, logs)
- **Daily notes** — session summaries

Memory flush before context compaction prevents the #1 agent failure: forgetting earlier context.

---

## Frontend

React 18 + TypeScript + Vite + Tailwind CSS. Dark/light theme.

**Layout:** Collapsible sidebar (hamburger) + main conversation + collapsible document panel.

**Key components:**
- Hero with time-aware greeting + animated orbital logo
- Research flow: plan tasks → tool activity feed → streaming synthesis
- Follow-up chat with full session context
- Document panel: rendered research report with download/copy
- Choice cards: interactive disambiguation (```choices code blocks)
- Rich artifacts: mermaid diagrams, charts, dashboard cards
- Sidebar: sessions list, memory peek, sources (upload/URL/paste/drop)
- Toast notifications

**Desktop app:** pywebview wraps FastAPI + built frontend in a native macOS window.

---

## Context Strategy

**Why this matters:** Context management is where most agents fail silently.

1. **Unified path** — every message goes through the same ReAct loop. No separate "research" vs "chat" code paths.
2. **Query rewriting** — resolves "them/it/this" using session synthesis before the LLM sees the message.
3. **Session-aware** — follow-ups include the full research synthesis (3000 tokens) in context.
4. **KB as tool** — vector search happens on-demand, not preloaded.
5. **Memory flush** — extracts key learnings to MEMORY.md before compaction.
6. **Structured output everywhere** — Pydantic models eliminate parsing failures.

---

## Evaluation Scenarios

| # | Scenario | Success Criteria |
|---|----------|-----------------|
| 1 | **Web research**: "Research GEPA architecture" | Plan with topic-specific tasks, web search results, cited synthesis |
| 2 | **Follow-up with tools**: Research topic, then "compare to transformers" | Query rewritten, tools called if needed, answer uses session context |
| 3 | **Document ingestion**: Upload PDF, then ask about its content | File ingested, KB search finds it, answer cites the document |
| 4 | **Cross-session knowledge**: Research topic A, new session asks related question | KB search finds prior research, answer builds on it |
| 5 | **Disambiguation**: Short ambiguous query | Choice cards rendered, user clicks option, research proceeds |

---

## Trade-offs & Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Agent framework | None (custom) | Assignment requirement |
| LLM provider | OpenAI (abstracted) | Provided API key; three-tier strategy optimizes cost |
| Web search | OpenAI native (Responses API) | Zero extra API keys needed |
| Vector DB | LanceDB (embedded) | Zero config, pip install |
| Structured output | Pydantic + `parse()` | Type-safe, zero parsing failures |
| Event protocol | AG-UI | Open standard, typed events |
| Frontend | React + Vite (custom) | No CopilotKit dependency (pulls LangChain) |
| KB visibility | Invisible tool | Grows silently, no management overhead |
| Reasoning | gpt-5.1 at `high` | Defaults to `none` — must be explicit |

## Time Spent

| Phase | Time | What |
|-------|------|------|
| Research & Design | ~2h | Analyzed claude-code, OpenClaw, GPT-Researcher; designed architecture |
| Core Backend | ~3h | LLM provider, tools, knowledge store, memory, agent loop |
| Frontend | ~3h | React app, dark/light theme, streaming, document panel |
| Iteration & Fixes | ~3h | ReAct loop, AG-UI events, structured output, UX refinements |
| Polish & Deliverables | ~1h | README, git, transcripts |

## Future Improvements

- **Full AG-UI compliance** with CopilotKit frontend (blocked by LangChain transitive dep)
- **Streaming synthesis** during research (currently streams in follow-up only)
- **Model picker** in the UI
- **Source management** — view/remove KB entries
- **Semantic search over session notes** — embed daily notes for better recall
- **Multi-turn plan refinement** — user can modify the plan before execution
- **Export** — PDF/DOCX output from the document panel

---

## Project Structure

```
planex/
├── main.py                 # CLI entry point
├── desktop.py              # Native macOS app (pywebview)
├── CLAUDE.md               # Claude Code guidance
├── core/
│   ├── agent.py            # Main orchestrator
│   ├── llm.py              # Three-tier LLM (chat, chat_parse, chat_stream, embed)
│   ├── models.py           # ALL Pydantic models for structured output
│   ├── react_loop.py       # Unified ReAct loop with AG-UI events
│   ├── planner.py          # Goal → structured plan
│   ├── executor.py         # Parallel task execution + synthesis
│   ├── context.py          # Context assembly pipeline
│   ├── knowledge.py        # LanceDB vector store (KBChunkMetadata)
│   ├── memory.py           # MEMORY.md + daily notes + flush
│   ├── state.py            # Session state + persistence
│   └── onboarding.py       # First-run setup
├── tools/
│   ├── base.py             # Tool ABC + registry
│   ├── web_search.py       # OpenAI native web search
│   ├── read_url.py         # URL content extraction
│   ├── local_search.py     # Ripgrep-style file search
│   ├── knowledge_search.py # KB vector search
│   ├── ingest.py           # Document ingestion
│   ├── file_ops.py         # Read/write files
│   └── time_tool.py        # Current date/time
├── dashboard/
│   └── app.py              # FastAPI: /api/turn (SSE), REST endpoints
├── cli/
│   └── app.py              # Rich terminal CLI
├── frontend/
│   ├── src/App.tsx          # Main layout (sidebar + conversation + doc panel)
│   ├── src/api/client.ts    # REST + AG-UI SSE consumer
│   ├── src/stores/          # Zustand state
│   └── src/components/      # React components
├── assets/
│   └── icon.svg/png         # Planex orbital logo
├── examples/
│   └── sample_docs/         # Demo documents
└── docs/
    └── specs/               # Design specification
```
