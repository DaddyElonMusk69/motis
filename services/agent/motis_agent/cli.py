"""
Motis CLI — Run the master agent locally without a platform.

Usage:
    python -m motis_agent.cli                          # interactive REPL
    python -m motis_agent.cli --model gpt-4o           # override model
    python -m motis_agent.cli --one-shot "What is BTC funding rate?"
    motis-chat                                          # if installed via pip

What this enables vs. the web platform:
  ✓ Full agent loop (ReAct, tool calls, MoA, sub-agents)
  ✓ All finance skills (data, SMC, technical, macro, reporting)
  ✓ Web search + fetch
  ✓ Sandboxed terminal (Python execution)
  ✓ Per-session memory (SQLite file at ~/.motis/memory.db)
  ✗ Operator management (no platform runtime)
  ✗ Live/paper trade execution (no exchange keys — MCP not running)
  ✗ Marketplace / Arena (platform-only)

Environment:
    MOTIS_API_KEY      Required. OpenAI-compatible API key.
    MOTIS_BASE_URL     Optional. Default: https://api.openai.com/v1
    MOTIS_MODEL        Optional. Default: gpt-4o
    BRAVE_API_KEY      Optional. Enables web search.
    TAVILY_API_KEY     Optional. Fallback web search.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

# ── Optional rich for pretty output ───────────────────────────────────────────
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.rule import Rule
    from rich.spinner import Spinner
    from rich.live import Live
    _RICH = True
except ImportError:
    _RICH = False


# ── Local (SQLite) context ─────────────────────────────────────────────────────

def _build_local_context(
    model: str,
    api_key: str,
    base_url: str,
    session_dir: Path,
) -> "UserContext":
    """
    Build a UserContext that uses local SQLite for memory and stubs for
    operator/exchange features. No PostgreSQL required.

    Memory is persisted in ~/.motis/memory.db across sessions.
    Operators/exchange tools are silently disabled.
    """
    from motis_agent.context import ModelConfig, UserContext

    # Patch __post_init__ to inject local backends instead of PG
    _patch_context_for_local(session_dir)

    user_id = _get_or_create_local_user_id(session_dir)

    return UserContext(
        user_id=user_id,
        email="local@cli",
        model_config=ModelConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
        ),
        conversation_id=uuid4(),
    )


def _patch_context_for_local(session_dir: Path) -> None:
    """
    Monkey-patch UserContext.__post_init__ to use local backends.
    Called once before constructing the context.

    Swaps:
      PostgresMemoryProvider  →  SQLiteMemoryProvider (local file)
      OperatorRegistry        →  StubOperatorRegistry (no-op, no operators)
      OperatorService         →  StubOperatorService
      SkillRegistry           →  same (finance skills don't need DB)
    """
    import motis_agent.context as ctx_module
    from motis_agent.context import UserContext

    sqlite_path = session_dir / "memory.db"

    def _local_post_init(self):
        from motis_agent.core.memory import MemoryStore
        from motis_agent.core.memory_manager import MemoryManager
        from motis_agent.core.skills import SkillRegistry
        from motis_agent.cli_backends import (
            SQLiteMemoryProvider,
            StubOperatorRegistry,
            StubOperatorService,
        )

        # SQLite-backed memory — no Postgres
        self.memory = MemoryStore.__new__(MemoryStore)  # skip PG __init__
        self.memory_manager = MemoryManager(
            providers=[SQLiteMemoryProvider(str(sqlite_path), user_id=self.user_id)]
        )
        # Finance skills work in CLI; operators/exchange don't
        self.skill_registry = SkillRegistry(user_id=self.user_id)
        self.operator_registry = StubOperatorRegistry(user_id=self.user_id)
        self.operator_service = StubOperatorService()

    UserContext.__post_init__ = _local_post_init


def _get_or_create_local_user_id(session_dir: Path) -> UUID:
    """Persist a stable local user ID across sessions."""
    id_file = session_dir / "user_id"
    if id_file.exists():
        return UUID(id_file.read_text().strip())
    uid = uuid4()
    session_dir.mkdir(parents=True, exist_ok=True)
    id_file.write_text(str(uid))
    return uid


# ── REPL ──────────────────────────────────────────────────────────────────────

class MotisREPL:
    """
    Interactive terminal REPL for the Motis master agent.
    Uses rich for pretty output when available, falls back to plain text.
    """

    def __init__(self, ctx: "UserContext"):
        self.ctx = ctx
        self.console = Console() if _RICH else None
        self._history: list[str] = []

    def _print(self, text: str, style: str = "") -> None:
        if self.console:
            self.console.print(text, style=style)
        else:
            print(text)

    def _print_md(self, text: str) -> None:
        if self.console:
            self.console.print(Markdown(text))
        else:
            print(text)

    def _rule(self, title: str = "") -> None:
        if self.console:
            self.console.print(Rule(title, style="dim"))
        else:
            print(f"{'─' * 60} {title}")

    def _prompt(self) -> str:
        if self.console:
            return Prompt.ask("\n[bold green]You[/bold green]")
        return input("\nYou: ")

    def _banner(self) -> None:
        if self.console:
            self.console.print(Panel.fit(
                "[bold cyan]Motis Master Agent[/bold cyan]  [dim](CLI mode)[/dim]\n"
                f"[dim]Model: {self.ctx.model_config.model}  •  "
                f"Memory: ~/.motis/memory.db  •  "
                "Type [bold]exit[/bold] or [bold]quit[/bold] to stop[/dim]",
                border_style="cyan",
            ))
        else:
            print("=" * 60)
            print("  Motis Master Agent  (CLI mode)")
            print(f"  Model: {self.ctx.model_config.model}")
            print("  Memory: ~/.motis/memory.db")
            print("=" * 60)

    def _format_tool_event(self, event: dict) -> str:
        tool = event.get("tool", "?")
        if event["type"] == "tool_call":
            args = event.get("args", {})
            # Show a compact arg summary
            summary = json.dumps(args, ensure_ascii=False)
            if len(summary) > 80:
                summary = summary[:77] + "..."
            return f"⚙  {tool}({summary})"
        elif event["type"] == "tool_result":
            ok = event.get("ok", True)
            icon = "✓" if ok else "✗"
            return f"  {icon} {tool} → done"
        return ""

    async def run_once(self, message: str) -> None:
        """Run a single non-interactive query and exit."""
        from motis_agent.core.loop import MotisAgentLoop
        loop = MotisAgentLoop(self.ctx)
        response_parts: list[str] = []

        async for event in loop.stream(message):
            t = event.get("type")
            if t == "text_delta":
                response_parts.append(event.get("text", ""))
                sys.stdout.write(event.get("text", ""))
                sys.stdout.flush()
            elif t in ("tool_call", "tool_result"):
                line = self._format_tool_event(event)
                if line:
                    print(f"\n{line}", file=sys.stderr)
            elif t == "error":
                print(f"\nError: {event.get('message')}", file=sys.stderr)

        print()  # final newline

    async def run_interactive(self) -> None:
        """Interactive multi-turn REPL."""
        from motis_agent.core.loop import MotisAgentLoop

        self._banner()
        self._print(
            "[dim]Operator tools disabled in CLI mode. "
            "Finance skills, web search, and terminal are available.[/dim]"
            if _RICH else
            "Note: Operator tools disabled in CLI mode."
        )

        # One loop per conversation (reuses message history across turns)
        loop = MotisAgentLoop(self.ctx)

        while True:
            try:
                user_input = self._prompt()
            except (EOFError, KeyboardInterrupt):
                self._print("\n[dim]Goodbye.[/dim]" if _RICH else "\nGoodbye.")
                break

            if user_input.strip().lower() in ("exit", "quit", "bye", "q"):
                self._print("\n[dim]Goodbye.[/dim]" if _RICH else "\nGoodbye.")
                break

            if not user_input.strip():
                continue

            self._history.append(user_input)
            self._rule("Motis")

            response_parts: list[str] = []
            tool_lines: list[str] = []

            if _RICH:
                # Stream response directly with live tool status
                with self.console.status("[dim]Thinking...[/dim]", spinner="dots"):
                    # Collect until first text_delta, then drop spinner
                    pass

            try:
                async for event in loop.stream(user_input):
                    t = event.get("type")

                    if t == "text_delta":
                        chunk = event.get("text", "")
                        response_parts.append(chunk)
                        if not _RICH:
                            sys.stdout.write(chunk)
                            sys.stdout.flush()

                    elif t == "tool_call":
                        line = self._format_tool_event(event)
                        if _RICH:
                            self.console.print(f"[dim]{line}[/dim]")
                        else:
                            print(f"\n{line}", file=sys.stderr)

                    elif t == "tool_result":
                        line = self._format_tool_event(event)
                        if _RICH and line:
                            self.console.print(f"[dim]{line}[/dim]")

                    elif t == "message_end":
                        pass  # handled by printing accumulated response

                    elif t == "error":
                        msg = event.get("message", "Unknown error")
                        if _RICH:
                            self.console.print(f"[red]Error: {msg}[/red]")
                        else:
                            print(f"\nError: {msg}", file=sys.stderr)

            except KeyboardInterrupt:
                self._print("\n[dim](Interrupted)[/dim]" if _RICH else "\n(Interrupted)")
                continue

            # Print accumulated response
            full_response = "".join(response_parts)
            if full_response:
                if _RICH:
                    self._print_md(full_response)
                else:
                    print()  # newline after streaming


# ── Entrypoint ────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="motis-chat",
        description="Motis Master Agent — CLI mode (no platform required)",
    )
    p.add_argument(
        "--model",
        default=os.environ.get("MOTIS_MODEL", "gpt-4o"),
        help="Model name (default: MOTIS_MODEL env or gpt-4o)",
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get("MOTIS_API_KEY") or os.environ.get("OPENAI_API_KEY", ""),
        help="API key (default: MOTIS_API_KEY env)",
    )
    p.add_argument(
        "--base-url",
        default=os.environ.get("MOTIS_BASE_URL", "https://api.openai.com/v1"),
        help="OpenAI-compatible base URL",
    )
    p.add_argument(
        "--one-shot", "-q",
        metavar="PROMPT",
        default=None,
        help="Run a single prompt non-interactively and exit",
    )
    p.add_argument(
        "--session-dir",
        default=str(Path.home() / ".motis"),
        help="Directory for persistent memory and user ID (default: ~/.motis)",
    )
    return p.parse_args()


async def _main() -> None:
    args = _parse_args()

    if not args.api_key:
        print(
            "Error: No API key found.\n"
            "Set MOTIS_API_KEY (or OPENAI_API_KEY) in your environment, "
            "or pass --api-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    session_dir = Path(args.session_dir)
    ctx = _build_local_context(
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        session_dir=session_dir,
    )

    repl = MotisREPL(ctx)

    if args.one_shot:
        await repl.run_once(args.one_shot)
    else:
        await repl.run_interactive()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
