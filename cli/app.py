"""Planex CLI — minimal subcommands for scripting and server management."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import click


def _bootstrap():
    """Load .env and run onboarding if needed."""
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(Path.home() / ".planex" / ".env")
    from core.onboarding import needs_onboarding, run_onboarding
    if needs_onboarding():
        if not run_onboarding():
            raise SystemExit(1)
        load_dotenv(Path.home() / ".planex" / ".env", override=True)


class _BootstrappedGroup(click.Group):
    def invoke(self, ctx):
        _bootstrap()
        return super().invoke(ctx)


@click.group(cls=_BootstrappedGroup)
def main():
    """Planex — AI Research Assistant."""
    pass


@main.command("serve")
@click.option("--port", "-p", default=8000, help="Server port")
def serve_cmd(port: int):
    """Start the web API server."""
    import uvicorn
    from dashboard.app import app as fastapi_app
    click.echo(f"Planex API on http://0.0.0.0:{port}")
    click.echo(f"API docs: http://localhost:{port}/docs")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)


@main.command("app")
def app_cmd():
    """Launch Planex as a desktop app."""
    from desktop import main as desktop_main
    desktop_main()


@main.command("run")
@click.argument("goal")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--transcript", "-t", is_flag=True, help="Output markdown transcript after completion")
def run_cmd(goal: str, yes: bool, transcript: bool):
    """Execute a research goal (non-interactive)."""
    asyncio.run(_run(goal, yes, transcript))


async def _run(goal: str, auto_confirm: bool, transcript: bool):
    from core.agent import Agent
    import sys

    if not transcript:
        click.echo(f"Goal: {goal}")

    agent = Agent()
    plan = await agent.plan(goal)

    if not transcript:
        click.echo(f"Plan: {plan.plan_title} ({len(plan.tasks)} tasks)")
    if not auto_confirm:
        if not click.confirm("Execute?", default=True):
            return

    synthesis = await agent.execute(plan)

    if transcript:
        _print_transcript(plan)
    else:
        click.echo(synthesis)


@main.command("ingest")
@click.argument("path")
def ingest_cmd(path: str):
    """Ingest documents into the knowledge base."""
    asyncio.run(_ingest(path))


async def _ingest(path: str):
    from core.agent import Agent
    agent = Agent()
    files, chunks = await agent.ingest(path)
    click.echo(f"Ingested {files} file(s), {chunks} chunks")


@main.command("status")
def status_cmd():
    """Show knowledge base stats and recent sessions."""
    asyncio.run(_status())


async def _status():
    from core.agent import Agent
    agent = Agent()
    info = agent.status()
    kb = info["knowledge_base"]
    click.echo(f"KB: {kb['documents']} docs, {kb['chunks']} chunks")
    for s in info["recent_sessions"]:
        click.echo(f"  {s['status']:<11} {s['plan_id']}  {s['goal'][:50]}")


def _print_transcript(plan_or_session):
    """Format a PlanState or session dict as markdown transcript."""
    from dataclasses import asdict

    # Handle both PlanState objects and dicts
    if hasattr(plan_or_session, 'plan_id'):
        s = asdict(plan_or_session)
    else:
        s = plan_or_session

    click.echo(f"# Research Session: {s['plan_title']}")
    click.echo(f"\n**Goal:** {s['goal']}")
    click.echo(f"**Session ID:** `{s['plan_id']}`")
    click.echo(f"**Status:** {s['status']}")
    click.echo()

    click.echo("## Plan\n")
    for t in s["tasks"]:
        status = t["status"] if isinstance(t, dict) else t.status
        title = t["title"] if isinstance(t, dict) else t.title
        tool = t.get("tool_hint", "") if isinstance(t, dict) else t.tool_hint
        tid = t["id"] if isinstance(t, dict) else t.id
        deps_list = t.get("depends_on", []) if isinstance(t, dict) else t.depends_on
        icon = "✅" if status == "completed" else "❌" if status == "failed" else "⬜"
        deps = f" *(after {', '.join(deps_list)})*" if deps_list else ""
        click.echo(f"- {icon} **{tid}**: {title} — `{tool}`{deps}")

    click.echo("\n## Execution Log\n")
    click.echo("| Time | Event | Tool | Detail |")
    click.echo("|------|-------|------|--------|")
    for log in s.get("logs", []):
        ts_raw = log["timestamp"] if isinstance(log, dict) else log.timestamp
        ts = ts_raw[11:19] if len(ts_raw) > 19 else ts_raw
        event = log["event_type"] if isinstance(log, dict) else log.event_type
        tool = (log.get("tool_name", "—") if isinstance(log, dict) else log.tool_name) or "—"
        out = log.get("output_summary", "") if isinstance(log, dict) else log.output_summary
        inp = log.get("input_summary", "") if isinstance(log, dict) else log.input_summary
        detail = ((out or inp) or "")[:80].replace("|", "\\|").replace("\n", " ")
        click.echo(f"| {ts} | {event} | {tool} | {detail} |")

    click.echo("\n## Synthesis\n")
    click.echo(s.get("synthesis", "*No synthesis*"))

    chat = s.get("chat_history", [])
    if chat:
        click.echo("\n## Follow-up Chat\n")
        for m in chat:
            content = m["content"] if isinstance(m, dict) else m.content
            role_key = m["role"] if isinstance(m, dict) else m.role
            role = "👤 **You**" if role_key == "user" else "🤖 **Planex**"
            click.echo(f"\n{role}:\n> {content[:300]}")


@main.command("transcript")
@click.argument("plan_id", required=False)
def transcript_cmd(plan_id: str | None):
    """Generate a markdown transcript from a session (latest if no ID given)."""
    import json

    sessions_dir = Path.home() / ".planex" / "sessions"
    if not sessions_dir.exists():
        click.echo("No sessions found.")
        return

    if plan_id:
        path = sessions_dir / f"{plan_id}.json"
        if not path.exists():
            click.echo(f"Session {plan_id} not found.")
            return
    else:
        files = sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            click.echo("No sessions found.")
            return
        path = files[0]

    session = json.loads(path.read_text())
    _print_transcript(session)


if __name__ == "__main__":
    main()
