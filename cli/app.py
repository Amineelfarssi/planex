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
    click.echo(f"Planex API on http://localhost:{port}")
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
def run_cmd(goal: str, yes: bool):
    """Execute a research goal (non-interactive)."""
    asyncio.run(_run(goal, yes))


async def _run(goal: str, auto_confirm: bool):
    from core.agent import Agent
    click.echo(f"Goal: {goal}")
    agent = Agent()
    plan = await agent.plan(goal)
    click.echo(f"Plan: {plan.plan_title} ({len(plan.tasks)} tasks)")
    if not auto_confirm:
        if not click.confirm("Execute?", default=True):
            return
    synthesis = await agent.execute(plan)
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


if __name__ == "__main__":
    main()
