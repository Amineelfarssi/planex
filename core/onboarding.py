"""First-run onboarding — collects API keys and creates ~/.planex/ structure."""

from __future__ import annotations

import os
from pathlib import Path

from rich.console import Console
from rich.text import Text
from rich.panel import Panel

PLANEX_DIR = Path.home() / ".planex"
ENV_FILE = PLANEX_DIR / ".env"

console = Console()


def needs_onboarding() -> bool:
    """Check if this is a first run (no API key configured)."""
    # Already have key in environment
    if os.getenv("OPENAI_API_KEY"):
        return False
    # Have a .env file with a key
    if ENV_FILE.exists():
        content = ENV_FILE.read_text()
        if "OPENAI_API_KEY=" in content:
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("OPENAI_API_KEY=") and not line.endswith("="):
                    val = line.split("=", 1)[1].strip()
                    if val and val != "sk-...":
                        return False
    return True


def run_onboarding() -> bool:
    """Interactive first-run setup. Returns True if successful."""
    console.print()
    console.print(Text("  Welcome to Planex!", style="bold blue"))
    console.print(Text("  Let's get you set up.", style="dim"))
    console.print()

    console.print(Panel(
        "Planex needs an OpenAI API key to work.\n"
        "Get one at: [cyan]https://platform.openai.com/api-keys[/cyan]",
        border_style="blue",
        padding=(1, 2),
    ))

    # --- OpenAI key ---
    openai_key = ""
    while not openai_key:
        try:
            openai_key = console.input(Text("  OpenAI API key: ", style="bold")).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            return False

        if not openai_key:
            console.print("  [yellow]API key is required to continue.[/yellow]")
        elif not openai_key.startswith("sk-"):
            console.print("  [yellow]That doesn't look like an OpenAI key (should start with sk-)[/yellow]")
            openai_key = ""

    # --- User name (for personalized greeting) ---
    console.print()
    try:
        user_name = console.input(Text("  Your name (for greeting): ", style="bold")).strip()
    except (EOFError, KeyboardInterrupt):
        user_name = ""

    # --- Tavily key (optional) ---
    console.print()
    console.print("  [dim]Tavily API key enables web search (optional, free tier).[/dim]")
    console.print("  [dim]Get one at: https://tavily.com[/dim]")
    try:
        tavily_key = console.input(Text("  Tavily API key (Enter to skip): ", style="bold")).strip()
    except (EOFError, KeyboardInterrupt):
        tavily_key = ""

    # --- Model selection ---
    console.print()
    console.print("  [dim]Choose your model tier (press Enter for defaults):[/dim]")
    console.print("  [dim]  fast=gpt-5.4-nano  smart=gpt-5.4-mini  strategic=gpt-5.4[/dim]")
    try:
        custom_models = console.input(Text("  Use defaults? [Y/n]: ", style="bold")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        custom_models = ""

    fast_model = "gpt-5.4-nano"
    smart_model = "gpt-5.4-mini"
    strategic_model = "gpt-5.4"

    if custom_models in ("n", "no"):
        try:
            fast_model = console.input(f"  Fast model [{fast_model}]: ").strip() or fast_model
            smart_model = console.input(f"  Smart model [{smart_model}]: ").strip() or smart_model
            strategic_model = console.input(f"  Strategic model [{strategic_model}]: ").strip() or strategic_model
        except (EOFError, KeyboardInterrupt):
            pass

    # --- Write config ---
    PLANEX_DIR.mkdir(parents=True, exist_ok=True)
    (PLANEX_DIR / "memory").mkdir(exist_ok=True)
    (PLANEX_DIR / "sources").mkdir(exist_ok=True)
    (PLANEX_DIR / "outputs").mkdir(exist_ok=True)
    (PLANEX_DIR / "sessions").mkdir(exist_ok=True)

    env_lines = [
        f"OPENAI_API_KEY={openai_key}",
        f"PLANEX_USER_NAME={user_name}" if user_name else "",
        "",
        f"PLANEX_FAST_MODEL={fast_model}",
        f"PLANEX_SMART_MODEL={smart_model}",
        f"PLANEX_STRATEGIC_MODEL={strategic_model}",
        "PLANEX_EMBEDDING_MODEL=text-embedding-3-small",
    ]
    if tavily_key:
        env_lines.insert(1, f"TAVILY_API_KEY={tavily_key}")

    ENV_FILE.write_text("\n".join(env_lines) + "\n")

    # Set in current process
    os.environ["OPENAI_API_KEY"] = openai_key
    if tavily_key:
        os.environ["TAVILY_API_KEY"] = tavily_key
    os.environ["PLANEX_FAST_MODEL"] = fast_model
    os.environ["PLANEX_SMART_MODEL"] = smart_model
    os.environ["PLANEX_STRATEGIC_MODEL"] = strategic_model

    console.print()
    console.print("  [green]Setup complete![/green]")
    console.print(f"  [dim]Config saved to {ENV_FILE}[/dim]")
    console.print(f"  [dim]Drop documents in ~/.planex/sources/ for auto-ingestion[/dim]")
    console.print()

    return True
