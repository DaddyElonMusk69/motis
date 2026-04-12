from __future__ import annotations

import builtins
import sys
from pathlib import Path


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

from motis_cli.setup import prompt_checklist, prompt_choice


def test_prompt_choice_uses_text_prompt(monkeypatch, capsys) -> None:
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")

    result = prompt_choice(
        "How would you like to set up Motis?",
        ["Quick setup", "Full setup"],
        0,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "How would you like to set up Motis?" in captured.out
    assert "Quick setup" in captured.out
    assert "Enter for default (1)" in captured.out


def test_prompt_checklist_uses_text_prompt(monkeypatch, capsys) -> None:
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")

    result = prompt_checklist(
        "Select platforms to configure:",
        ["Telegram", "Discord"],
        [0],
    )

    captured = capsys.readouterr()
    assert result == [0]
    assert "Select platforms to configure:" in captured.out
    assert "1. Telegram" in captured.out
    assert "Toggle by number, Enter to confirm." in captured.out
