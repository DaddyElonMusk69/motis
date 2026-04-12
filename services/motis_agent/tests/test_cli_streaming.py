from __future__ import annotations

import os
import sys
from pathlib import Path


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

import cli as cli_module
from motis_cli.config import DEFAULT_CONFIG


def _make_cli() -> cli_module.MotisCLI:
    cli = cli_module.MotisCLI.__new__(cli_module.MotisCLI)
    cli.show_reasoning = False
    cli._stream_box_opened = True
    cli._stream_buf = ""
    cli._stream_text_ansi = ""
    cli._stream_visible_text = ""
    cli._stream_last_partial_flush = 0.0
    cli._reasoning_box_opened = False
    cli._reasoning_buf = ""
    cli._deferred_content = ""
    cli._close_reasoning_box = lambda: None
    return cli


def test_default_config_enables_streaming() -> None:
    assert DEFAULT_CONFIG["display"]["streaming"] is True


def test_emit_stream_text_buffers_partial_paragraph_until_wrap_or_flush(monkeypatch) -> None:
    cli = _make_cli()
    calls: list[tuple[str, str, bool]] = []

    def fake_cprint(text: str, *, end: str = "\n", flush: bool = True) -> None:
        calls.append((text, end, flush))

    monkeypatch.setattr(cli_module, "_cprint", fake_cprint)
    monkeypatch.setattr(cli_module.time, "monotonic", lambda: 1.0)
    monkeypatch.setattr(cli_module.shutil, "get_terminal_size", lambda: os.terminal_size((80, 24)))

    cli._emit_stream_text("This should appear before the model emits a newline.")

    assert calls == []
    assert cli._stream_buf == "This should appear before the model emits a newline."


def test_emit_stream_text_hard_wraps_long_unbroken_token(monkeypatch) -> None:
    cli = _make_cli()
    calls: list[tuple[str, str, bool]] = []

    def fake_cprint(text: str, *, end: str = "\n", flush: bool = True) -> None:
        calls.append((text, end, flush))

    monkeypatch.setattr(cli_module, "_cprint", fake_cprint)
    monkeypatch.setattr(cli_module.time, "monotonic", lambda: 1.0)
    monkeypatch.setattr(cli_module.shutil, "get_terminal_size", lambda: os.terminal_size((40, 24)))
    cli._get_tui_terminal_width = lambda default=(80, 24): 40

    cli._emit_stream_text("x" * 40)

    assert calls == [("x" * 36, "\n", True)]
    assert cli._stream_buf == "x" * 4


def test_emit_stream_text_prefers_live_tui_width_over_shutil(monkeypatch) -> None:
    cli = _make_cli()
    calls: list[tuple[str, str, bool]] = []

    def fake_cprint(text: str, *, end: str = "\n", flush: bool = True) -> None:
        calls.append((text, end, flush))

    monkeypatch.setattr(cli_module, "_cprint", fake_cprint)
    monkeypatch.setattr(cli_module.time, "monotonic", lambda: 1.0)
    monkeypatch.setattr(cli_module.shutil, "get_terminal_size", lambda: os.terminal_size((40, 24)))
    cli._get_tui_terminal_width = lambda default=(80, 24): 80

    cli._emit_stream_text("Yes, I can communicate in English. How can I assist you today?")

    assert calls == []
    assert cli._stream_buf == "Yes, I can communicate in English. How can I assist you today?"


def test_flush_stream_emits_remaining_buffer_before_border(monkeypatch) -> None:
    cli = _make_cli()
    cli._stream_buf = "newline."
    calls: list[tuple[str, str, bool]] = []

    def fake_cprint(text: str, *, end: str = "\n", flush: bool = True) -> None:
        calls.append((text, end, flush))

    monkeypatch.setattr(cli_module, "_cprint", fake_cprint)
    monkeypatch.setattr(cli_module.shutil, "get_terminal_size", lambda: os.terminal_size((20, 24)))

    cli._flush_stream()

    assert calls[0] == ("newline.", "\n", True)
    assert "╰" in calls[1][0]


def test_should_skip_final_panel_only_on_exact_match() -> None:
    cli = _make_cli()
    cli._stream_started = True
    cli._stream_box_opened = True
    cli._stream_visible_text = "Full streamed answer."

    assert cli._should_skip_final_panel("Full streamed answer.", is_error_response=False) is True
    assert cli._should_skip_final_panel("Full streamed answer. Plus more.", is_error_response=False) is False
    assert cli._should_skip_final_panel("Full streamed answer.", is_error_response=True) is False
