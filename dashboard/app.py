"""FastAPI backend for Planex — unified ReAct loop with AG-UI events.

Endpoints:
  POST /api/turn              — unified ReAct loop (SSE stream of AG-UI events)
  POST /api/upload             — upload files to KB
  POST /api/ingest             — ingest from local path
  POST /api/ingest-url         — fetch URL and ingest
  POST /api/ingest-text        — ingest pasted text
  POST /api/suggest-clarifications — generate disambiguation options
  GET  /api/status             — KB stats + recent sessions
  GET  /api/reports            — list sessions
  GET  /api/reports/{id}       — session details
  GET  /api/greeting           — time-aware greeting
  GET  /api/health             — health check
  GET  /api/knowledge/stats    — KB statistics
  POST /api/knowledge/search   — search KB
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()
load_dotenv(Path.home() / ".planex" / ".env")

app = FastAPI(title="Planex API", version="0.1.0")

# Serve built frontend if it exists
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(_frontend_dist / "index.html")

    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton agent
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        from core.agent import Agent
        _agent = Agent()
    return _agent


# ---------------------------------------------------------------------------
# Unified turn — ReAct loop with AG-UI events (SSE)
# ---------------------------------------------------------------------------

class TurnRequest(BaseModel):
    message: str
    chat_history: list[dict] = []
    session_id: str | None = None


@app.post("/api/turn")
async def unified_turn(req: TurnRequest):
    """Every user message goes through Agent.turn() → AG-UI SSE events."""
    from fastapi.responses import StreamingResponse
    from core.react_loop import run_turn

    agent = _get_agent()
    return StreamingResponse(
        run_turn(agent, req.message, req.chat_history, req.session_id),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Clarification
# ---------------------------------------------------------------------------

@app.post("/api/suggest-clarifications")
async def suggest_clarifications(query: str = ""):
    """LLM generates disambiguation options for ambiguous queries."""
    if not query:
        return {"options": []}

    from core.models import ClarificationRequest as ClarModel

    agent = _get_agent()
    try:
        result: ClarModel = await agent.llm.chat_parse(
            messages=[{
                "role": "user",
                "content": (
                    "The user submitted this research query which may be ambiguous. "
                    "Generate 3-4 specific research directions.\n\n"
                    f"User query: \"{query}\""
                ),
            }],
            response_model=ClarModel,
            tier="fast",
        )
        return {"options": [o.model_dump() for o in result.options]}
    except Exception:
        return {"options": []}


# ---------------------------------------------------------------------------
# Greeting
# ---------------------------------------------------------------------------

@app.get("/api/greeting")
async def greeting():
    """Time-aware greeting."""
    now = datetime.now()
    hour = now.hour
    period = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"

    name = os.getenv("PLANEX_USER_NAME", "")
    if not name:
        agent = _get_agent()
        memory = agent.memory.load_memory()
        for line in memory.split("\n"):
            if "name:" in line.lower() or "user:" in line.lower():
                name = line.split(":")[-1].strip()
                break

    return {
        "period": period,
        "name": name,
        "date": now.strftime("%A, %B %d, %Y"),
        "time": now.strftime("%H:%M"),
    }


# ---------------------------------------------------------------------------
# Document ingestion
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    path: str


class IngestUrlRequest(BaseModel):
    url: str


class IngestTextRequest(BaseModel):
    text: str
    title: str = ""


@app.post("/api/ingest")
async def ingest(req: IngestRequest):
    agent = _get_agent()
    files, chunks = await agent.ingest(req.path)
    stats = agent.knowledge.get_stats()
    return {"files_ingested": files, "chunks_created": chunks, "total_chunks": stats["chunks"]}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    agent = _get_agent()
    upload_dir = Path.home() / ".planex" / "sources"
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)

    chunks = await agent.knowledge.ingest_file(str(dest), "local_file", "user_upload")
    stats = agent.knowledge.get_stats()
    return {
        "filename": file.filename,
        "chunks_created": chunks,
        "already_exists": chunks == 0,
        "kb_total_chunks": stats.get("chunks", 0),
    }


@app.post("/api/ingest-url")
async def ingest_url(req: IngestUrlRequest):
    agent = _get_agent()
    from tools.read_url import ReadUrlTool
    reader = ReadUrlTool()
    result = await reader.execute(url=req.url)
    if not result.success:
        return {"error": result.data, "chunks_created": 0}

    chunks = await agent.knowledge.ingest_text(
        text=result.data,
        source=req.url,
        source_type="web_page",
        ingested_by="user_upload",
        title=result.metadata.get("title", req.url[:50]),
    )
    return {"url": req.url, "chunks_created": chunks, "title": result.metadata.get("title", "")}


@app.post("/api/ingest-text")
async def ingest_text_endpoint(req: IngestTextRequest):
    agent = _get_agent()
    chunks = await agent.knowledge.ingest_text(
        text=req.text,
        source=f"pasted:{req.title or 'untitled'}",
        source_type="local_file",
        ingested_by="user_upload",
        title=req.title or "Pasted text",
    )
    return {"chunks_created": chunks, "title": req.title or "Pasted text"}


# ---------------------------------------------------------------------------
# Sessions + status
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "planex", "version": "0.1.0"}


@app.get("/api/status")
async def status():
    agent = _get_agent()
    return agent.status()


@app.get("/api/reports")
async def list_reports():
    agent = _get_agent()
    return agent.state.list_sessions(limit=50)


@app.get("/api/reports/{plan_id}")
async def get_report(plan_id: str):
    agent = _get_agent()
    plan = agent.state.load(plan_id)
    if not plan:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return {
        "plan_id": plan.plan_id,
        "goal": plan.goal,
        "plan_title": plan.plan_title,
        "status": plan.status,
        "created_at": plan.created_at,
        "synthesis": plan.synthesis,
        "tasks": [
            {
                "id": t.id, "title": t.title, "description": t.description,
                "status": t.status, "tool_hint": t.tool_hint,
                "depends_on": t.depends_on, "result_summary": t.result_summary,
                "started_at": t.started_at, "completed_at": t.completed_at,
            }
            for t in plan.tasks
        ],
        "chat_history": [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in plan.chat_history
        ],
        "memory_extracts": plan.memory_extracts,
        "logs": [
            {
                "timestamp": l.timestamp, "event_type": l.event_type,
                "task_id": l.task_id, "tool_name": l.tool_name,
                "output_summary": l.output_summary,
            }
            for l in plan.logs
        ],
    }


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

@app.get("/api/knowledge/stats")
async def knowledge_stats():
    agent = _get_agent()
    return agent.knowledge.get_stats()


@app.post("/api/knowledge/search")
async def knowledge_search(query: str, top_k: int = 5):
    agent = _get_agent()
    results = await agent.knowledge.search(query, top_k=top_k)
    return [
        {
            "doc_title": r.get("doc_title", ""),
            "source": r.get("source", ""),
            "source_type": r.get("source_type", ""),
            "text": r.get("text", "")[:500],
        }
        for r in results
    ]


def run_server():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_server()
