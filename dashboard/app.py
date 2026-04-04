"""FastAPI backend for Planex — unified ReAct loop with AG-UI events.

Endpoints:
  POST /api/turn          — unified ReAct loop (SSE stream of AG-UI events)
  POST /api/ingest        — ingest documents
  POST /api/upload        — upload files
  GET  /api/status        — KB stats + recent sessions
  GET  /api/reports       — list past research sessions
  GET  /api/reports/{id}  — get a specific session's results
  GET  /api/greeting      — time-aware greeting
  GET  /api/health        — health check
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Bootstrap env
load_dotenv()
load_dotenv(Path.home() / ".planex" / ".env")

app = FastAPI(title="Planex API", version="0.1.0")

# Serve built frontend if it exists
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    from fastapi.responses import FileResponse

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


# Singleton agent (avoid re-init on every request)
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        from core.agent import Agent
        _agent = Agent()
    return _agent


# ---------------------------------------------------------------------------
# WebSocket — main research flow
# ---------------------------------------------------------------------------

async def _ws_send(ws: WebSocket, msg_type: str, content: str, output: str = ""):
    """Send a message in GPT-Researcher format: {type, content, output}."""
    await ws.send_json({"type": msg_type, "content": content, "output": output})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    try:
        while True:
            data = await ws.receive_text()

            if data == "ping":
                await ws.send_text("pong")
                continue

            if not data.startswith("start "):
                continue

            try:
                config = json.loads(data[6:])
            except json.JSONDecodeError:
                await _ws_send(ws, "error", "Invalid JSON", "Could not parse request")
                continue

            task = config.get("task", "")
            if not task:
                await _ws_send(ws, "error", "No task", "Please provide a research goal")
                continue

            agent = _get_agent()

            # Route intent
            await _ws_send(ws, "logs", "Analyzing request...", "")
            intent = await _route_intent(agent, task)
            await _ws_send(ws, "logs", f"Intent: {intent}", "")

            if intent == "chat":
                await _ws_handle_chat(ws, agent, task)
            elif intent == "kb_query":
                await _ws_handle_kb_query(ws, agent, task)
            else:
                await _ws_handle_research(ws, agent, task)

            await _ws_send(ws, "path", "complete", "")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await _ws_send(ws, "error", "Server error", str(e))
        except Exception:
            pass


async def _rewrite_query(agent, raw_query: str, conversation: list[dict], session_context: str = "") -> str:
    """Rewrite a follow-up query into a standalone, fully-formed question.

    CRITICAL: Resolves "them", "it", "this", "those" etc. using the session's
    research topic. If the session was about GEPA and user says "compare them to X",
    "them" = GEPA.
    """
    if not conversation and not session_context:
        return raw_query
    if len(raw_query.split()) > 25:
        return raw_query

    history = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:150]}"
        for m in conversation[-6:]
    )

    prompt = (
        "Rewrite the user's message into a standalone question. "
        "CRITICAL: Resolve ALL pronouns and references using the research context.\n\n"
        "Examples:\n"
        "- Research was about 'GEPA architecture', user says 'compare them to transformers' → "
        "'Compare GEPA architecture to transformer architecture'\n"
        "- Research was about 'cybersecurity trends', user says 'what about the legal implications?' → "
        "'What are the legal implications of cybersecurity trends?'\n\n"
        "Return ONLY the rewritten query.\n\n"
    )
    if session_context:
        prompt += f"RESEARCH CONTEXT (this is what the session is about):\n{session_context[:800]}\n\n"
    if history:
        prompt += f"CONVERSATION:\n{history}\n\n"
    prompt += f"USER'S MESSAGE: {raw_query}\n\nREWRITTEN:"

    from core.models import RewrittenQuery

    try:
        result: RewrittenQuery = await agent.llm.chat_parse(
            messages=[{"role": "user", "content": prompt}],
            response_model=RewrittenQuery,
            tier="fast",
        )
        return result.query if result.changed and result.query else raw_query
    except Exception:
        return raw_query


async def _route_intent(agent, message: str) -> str:
    """Classify intent using structured output."""
    from core.models import IntentClassification

    try:
        result: IntentClassification = await agent.llm.chat_parse(
            messages=[{
                "role": "user",
                "content": (
                    "Classify this message:\n"
                    '- "chat": greetings, simple questions, meta questions\n'
                    '- "research": needs web search, multi-source analysis, report writing\n'
                    '- "kb_query": answerable from existing knowledge base\n\n'
                    f'Message: "{message}"'
                ),
            }],
            response_model=IntentClassification,
            tier="fast",
        )
        if result.intent in ("chat", "research", "kb_query"):
            return result.intent
    except Exception:
        pass
    return "chat" if len(message.split()) <= 5 else "research"


async def _ws_handle_chat(ws, agent, message):
    memory = agent.memory.load_memory()
    kb = agent.knowledge.get_stats()
    system = (
        "You are Planex, an AI research assistant. Be helpful and concise.\n"
        f"KB: {kb['chunks']} chunks, {kb.get('documents', 0)} docs.\n"
    )
    if memory.strip():
        system += f"\nUser context:\n{memory[:500]}"

    resp = await agent.llm.chat(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": message}],
        tier="fast",
    )
    await _ws_send(ws, "report", "answer", resp.content or "")


async def _ws_handle_kb_query(ws, agent, query):
    await _ws_send(ws, "logs", "Searching knowledge base...", query)
    results = await agent.knowledge.search(query, top_k=5, use_rag_fusion=True)

    if not results:
        await _ws_send(ws, "report", "answer", "No relevant documents found. Try ingesting documents first.")
        return

    for r in results:
        await _ws_send(ws, "logs", "Source found", f"{r.get('doc_title', 'unknown')} ({r.get('source_type', '')})")

    context = "\n\n".join(f"[{r.get('doc_title', '?')}]: {r.get('text', '')[:500]}" for r in results)
    await _ws_send(ws, "logs", "Synthesizing...", "")

    resp = await agent.llm.chat(
        messages=[
            {"role": "system", "content": "Answer based on retrieved documents. Cite sources. Be concise."},
            {"role": "user", "content": f"Question: {query}\n\nDocuments:\n{context}"},
        ],
        tier="smart",
    )
    await _ws_send(ws, "report", "answer", resp.content or "")


async def _ws_handle_research(ws, agent, goal):
    start = time.time()

    # Plan
    await _ws_send(ws, "logs", "Creating research plan...", "")
    plan = await agent.plan(goal)
    await _ws_send(ws, "logs", f"Plan: {plan.plan_title}", f"{len(plan.tasks)} tasks")

    for task in plan.tasks:
        deps = f" (after {', '.join(task.depends_on)})" if task.depends_on else ""
        await _ws_send(ws, "logs", f"Task: {task.title}", f"{task.tool_hint}{deps}")

    # Execute
    await _ws_send(ws, "logs", "Executing...", "")

    async def on_update_async(task, status):
        icon = "\u2713" if status == "completed" else "\u2717" if status == "failed" else "\u25d4"
        await _ws_send(ws, "logs", f"{icon} {task.title}", status)

    def on_update(task, status):
        task.status = status
        asyncio.get_event_loop().create_task(on_update_async(task, status))

    synthesis = await agent.execute(plan, on_task_update=on_update)

    # Stream report
    chunk_size = 100
    for i in range(0, len(synthesis), chunk_size):
        await _ws_send(ws, "report", "report_chunk", synthesis[i:i + chunk_size])
        await asyncio.sleep(0.02)

    await _ws_send(ws, "report_complete", "complete", synthesis)

    elapsed = time.time() - start
    tokens = sum(u.total for u in agent.llm.total_usage.values()) if agent.llm.total_usage else 0
    await _ws_send(ws, "logs", f"Done in {elapsed:.1f}s", f"Tokens: {tokens}")


# ---------------------------------------------------------------------------
# REST — chat, ingest, status, reports
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    messages: list[dict] = []
    research_id: str | None = None


class IngestRequest(BaseModel):
    path: str


# ---------------------------------------------------------------------------
# Clarification / AskUser (like Claude Code's AskUserQuestion)
# ---------------------------------------------------------------------------

class ClarifyRequest(BaseModel):
    question: str
    options: list[dict]  # [{label, description}]
    research_id: str | None = None


class ClarifyResponse(BaseModel):
    selected: str


@app.post("/api/clarify")
async def ask_clarification(req: ClarifyRequest):
    """Generate clarification options for ambiguous queries.

    Called by the frontend when the intent router detects ambiguity,
    or by the agent when it needs user input before proceeding.
    """
    return {"question": req.question, "options": req.options}


@app.post("/api/suggest-clarifications")
async def suggest_clarifications(query: str = ""):
    """LLM generates clarification options for an ambiguous query."""
    if not query:
        return {"options": []}

    from core.models import ClarificationRequest as ClarModel

    agent = _get_agent()
    try:
        result: ClarModel = await agent.llm.chat_parse(
            messages=[{
                "role": "user",
                "content": (
                    "The user submitted this research query which may be ambiguous or broad. "
                    "Generate 3-4 specific research directions they might mean.\n\n"
                    f"User query: \"{query}\""
                ),
            }],
            response_model=ClarModel,
            tier="fast",
        )
        return {"options": [o.model_dump() for o in result.options]}
    except Exception:
        return {"options": []}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "planex", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Unified turn endpoint — ReAct loop with AG-UI events (SSE)
# ---------------------------------------------------------------------------

class TurnRequest(BaseModel):
    message: str
    chat_history: list[dict] = []
    session_id: str | None = None


@app.post("/api/turn")
async def unified_turn(req: TurnRequest):
    """Unified ReAct loop — streams AG-UI events via SSE.

    Every user message (research or follow-up) goes through the same loop:
    1. Rewrite query (resolve references)
    2. Assemble context (memory + session + KB)
    3. ReAct: LLM decides → tool call → observe → repeat or respond
    4. Stream AG-UI events throughout
    """
    from fastapi.responses import StreamingResponse
    from core.react_loop import run_turn

    agent = _get_agent()

    return StreamingResponse(
        run_turn(agent, req.message, req.chat_history, req.session_id),
        media_type="text/event-stream",
    )


@app.get("/api/greeting")
async def greeting():
    """Time-aware greeting like Claude Desktop."""
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        period = "morning"
    elif hour < 17:
        period = "afternoon"
    else:
        period = "evening"

    # Get user name from env (set during onboarding) or memory
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


import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")
_CHAT_TOKEN_BUDGET = 12_000  # compact when chat context exceeds this


def _count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


async def _compact_chat_history(agent, chat_history: list, session_context: str) -> tuple[str, list]:
    """Compact older chat turns into a summary + keep recent turns.

    Returns (compacted_summary, recent_messages).
    When total chat tokens > budget:
      1. Flush: extract important facts → MEMORY.md
      2. Compact: summarize older turns into one paragraph
      3. Keep: last 4 messages in full
    """
    if not chat_history:
        return "", []

    total = sum(_count_tokens(m.get("content", "")) for m in chat_history)
    if total <= _CHAT_TOKEN_BUDGET:
        return "", chat_history  # no compaction needed

    # Split: older turns to compact, recent to keep
    keep_count = min(4, len(chat_history))
    older = chat_history[:-keep_count]
    recent = chat_history[-keep_count:]

    # Flush important facts to MEMORY.md
    older_text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in older)
    await agent.memory.flush(older_text + "\n" + session_context[:500])

    # Compact older turns into summary
    resp = await agent.llm.chat(
        messages=[{
            "role": "user",
            "content": (
                "Summarize this conversation history in one concise paragraph. "
                "Preserve key facts, decisions, and user preferences.\n\n"
                + older_text[:3000]
            ),
        }],
        tier="fast",
    )
    summary = resp.content or older_text[:500]
    return summary, recent


@app.post("/api/chat")
async def chat_turn(req: ChatRequest):
    """Unified turn handler: rewrite → route → assemble context → dispatch.

    Every user message goes through:
    1. Query rewriting (resolve references using conversation context)
    2. Intent routing (chat / kb_query / research)
    3. Context assembly from ALL memory layers + compaction if needed
    4. Dispatch to the right handler
    """
    agent = _get_agent()
    user_msg = req.messages[-1]["content"] if req.messages else ""
    if not user_msg:
        return {"role": "assistant", "content": "Please provide a message.", "intent": "error"}

    # Load session context if linked
    session_context = ""
    plan = None
    if req.research_id:
        plan = agent.state.load(req.research_id)
        if plan:
            session_context = (plan.synthesis or "")[:2000]

    # Step 1: Rewrite query (uses last 3 turns for reference resolution)
    rewritten = await _rewrite_query(agent, user_msg, req.messages[:-1], session_context)

    # Step 2: Compact chat history if too long
    compacted_summary, recent_messages = await _compact_chat_history(
        agent, req.messages, session_context
    )

    # Step 3: Assemble full context from ALL memory layers
    memory_md = agent.memory.load_memory()
    daily_notes = agent.memory.load_daily_notes()

    system_parts = [
        "You are Planex, an AI research assistant with a persistent knowledge base.",
        "Answer the user's question using the research context and knowledge base below.",
        "Use markdown formatting. Be thorough but concise. Cite sources when available.",
        "",
        "SCOPE: You are a RESEARCH assistant only. You can search, read, analyze, compare, and synthesize information.",
        "Do NOT suggest building dashboards, running models, writing code, deploying services, or executing anything.",
        "If asked to do something outside research scope, explain what you CAN do and offer relevant research instead.",
        "",
        "CHOICE CARDS: When you need to ask the user to choose between options (clarification,",
        "disambiguation, or scope decisions), you MUST use a ```choices code block — never list",
        "options as plain text (a/b/c, 1/2/3, or bullet points with 'or').",
        "Do NOT use choices for proactive 'next steps' or 'what else can I do' suggestions.",
        "Format: ```choices\\n{\"question\": \"...\", \"options\": [{\"label\": \"...\", \"description\": \"...\", \"value\": \"the full refined query\"}]}\\n```",
    ]
    if memory_md.strip():
        system_parts.append(f"\n[Long-term memory]\n{memory_md[:600]}")
    if daily_notes.strip():
        system_parts.append(f"\n[Recent session notes]\n{daily_notes[:400]}")
    if session_context:
        system_parts.append(f"\n[Current research findings — THIS is what the user is asking about]\n{session_context[:3000]}")
    if compacted_summary:
        system_parts.append(f"\n[Earlier in this conversation]\n{compacted_summary}")

    # Step 4: Try KB search with the rewritten query for additional context
    kb_context = ""
    try:
        results = await agent.knowledge.search(rewritten, top_k=3, use_rag_fusion=False)
        if results:
            kb_context = "\n\n".join(
                f"[{r.get('doc_title', '?')}]: {r.get('text', '')[:400]}"
                for r in results
            )
            system_parts.append(f"\n[Knowledge base results]\n{kb_context}")
    except Exception:
        pass

    system = "\n".join(system_parts)
    intent = "follow_up"

    # Step 5: Single LLM call with full context — no routing, no new plans
    msgs = [{"role": "system", "content": system}] + recent_messages

    # Check if client wants streaming (Accept: text/event-stream)
    resp = await agent.llm.chat(messages=msgs, tier="smart")
    answer = resp.content or ""

    # Save to session
    if plan:
        agent.state.add_chat_message(plan, "user", user_msg)
        agent.state.add_chat_message(plan, "assistant", answer)

    # Save to daily notes
    agent.memory.append_daily_note(
        f"**Chat Q:** {user_msg[:100]}\n**Chat A:** {answer[:200]}"
    )

    return {
        "role": "assistant",
        "content": answer,
        "intent": intent,
        "rewritten_query": rewritten if rewritten != user_msg else None,
    }


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming version of /api/chat — returns SSE tokens."""
    from fastapi.responses import StreamingResponse

    agent = _get_agent()
    user_msg = req.messages[-1]["content"] if req.messages else ""
    if not user_msg:
        return {"error": "No message"}

    session_context = ""
    plan = None
    if req.research_id:
        plan = agent.state.load(req.research_id)
        if plan:
            session_context = (plan.synthesis or "")[:2000]

    rewritten = await _rewrite_query(agent, user_msg, req.messages[:-1], session_context)

    _, recent_messages = await _compact_chat_history(agent, req.messages, session_context)

    memory_md = agent.memory.load_memory()
    system_parts = [
        "You are Planex, an AI research assistant. Use markdown. Be concise. Cite sources.",
        "SCOPE: Research only — search, read, analyze, compare, synthesize. No code execution or deployments.",
    ]
    if session_context:
        system_parts.append(f"\n[Research context]\n{session_context[:3000]}")
    if memory_md.strip():
        system_parts.append(f"\n[Memory]\n{memory_md[:600]}")

    # KB search
    try:
        results = await agent.knowledge.search(rewritten, top_k=3, use_rag_fusion=False)
        if results:
            kb = "\n".join(f"[{r.get('doc_title','?')}]: {r.get('text','')[:300]}" for r in results)
            system_parts.append(f"\n[KB]\n{kb}")
    except Exception:
        pass

    system = "\n".join(system_parts)
    msgs = [{"role": "system", "content": system}] + recent_messages

    async def generate():
        full = ""
        # Send rewritten query hint
        if rewritten != user_msg:
            yield f"data: {json.dumps({'type': 'rewrite', 'query': rewritten})}\n\n"

        async for chunk in agent.llm.chat_stream(messages=msgs, tier="smart"):
            full += chunk
            yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'full': full})}\n\n"

        # Save to session + memory (after streaming completes)
        if plan:
            agent.state.add_chat_message(plan, "user", user_msg)
            agent.state.add_chat_message(plan, "assistant", full)
        agent.memory.append_daily_note(f"**Q:** {user_msg[:100]}\n**A:** {full[:200]}")

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/ingest")
async def ingest(req: IngestRequest):
    """Ingest documents from a local path."""
    agent = _get_agent()
    files, chunks = await agent.ingest(req.path)
    stats = agent.knowledge.get_stats()
    return {
        "files_ingested": files,
        "chunks_created": chunks,
        "total_documents": stats.get("documents", 0),
        "total_chunks": stats["chunks"],
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Upload a file and ingest it. Returns structured KBIngestResult."""
    agent = _get_agent()
    upload_dir = Path.home() / ".planex" / "sources"
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)

    chunks = await agent.knowledge.ingest_file(str(dest), "local_file", "user_upload")

    # Get metadata that was extracted during ingestion
    stats = agent.knowledge.get_stats()
    return {
        "filename": file.filename,
        "chunks_created": chunks,
        "already_exists": chunks == 0,
        "kb_total_chunks": stats.get("chunks", 0),
    }


class IngestUrlRequest(BaseModel):
    url: str


class IngestTextRequest(BaseModel):
    text: str
    title: str = ""


@app.post("/api/ingest-url")
async def ingest_url(req: IngestUrlRequest):
    """Fetch a URL and ingest its content into KB."""
    agent = _get_agent()
    # Use read_url tool to fetch content
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
    """Ingest pasted text into KB."""
    agent = _get_agent()
    chunks = await agent.knowledge.ingest_text(
        text=req.text,
        source=f"pasted:{req.title or 'untitled'}",
        source_type="local_file",
        ingested_by="user_upload",
        title=req.title or "Pasted text",
    )
    return {"chunks_created": chunks, "title": req.title or "Pasted text"}


@app.get("/api/status")
async def status():
    """KB stats + recent sessions."""
    agent = _get_agent()
    return agent.status()


@app.get("/api/reports")
async def list_reports():
    """List all research sessions."""
    agent = _get_agent()
    return agent.state.list_sessions(limit=50)


@app.get("/api/reports/{plan_id}")
async def get_report(plan_id: str):
    """Get a specific research session."""
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
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "tool_hint": t.tool_hint,
                "depends_on": t.depends_on,
                "result_summary": t.result_summary,
                "started_at": t.started_at,
                "completed_at": t.completed_at,
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
                "timestamp": l.timestamp,
                "event_type": l.event_type,
                "task_id": l.task_id,
                "tool_name": l.tool_name,
                "output_summary": l.output_summary,
            }
            for l in plan.logs
        ],
    }


@app.get("/api/knowledge/stats")
async def knowledge_stats():
    """Knowledge base statistics."""
    agent = _get_agent()
    return agent.knowledge.get_stats()


@app.post("/api/knowledge/search")
async def knowledge_search(query: str, top_k: int = 5):
    """Search the knowledge base."""
    agent = _get_agent()
    results = await agent.knowledge.search(query, top_k=top_k, use_rag_fusion=True)
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
