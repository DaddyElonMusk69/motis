from __future__ import annotations

import builtins
import importlib
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
MOTIS_CLI = REPO_ROOT / "services/upstream/hermes_agent/motis"


def _run_motis(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    runtime_env = os.environ.copy()
    if env:
        runtime_env.update(env)
    return subprocess.run(
        [sys.executable, str(MOTIS_CLI), *args],
        capture_output=True,
        text=True,
        env=runtime_env,
        check=False,
    )


def test_motis_help_smoke() -> None:
    result = _run_motis("--help")

    assert result.returncode == 0, result.stderr
    assert "Motis - AI assistant with tool-calling capabilities" in result.stdout
    assert "chat" in result.stdout
    assert "doctor" in result.stdout


def test_motis_chat_help_smoke() -> None:
    result = _run_motis("chat", "--help")

    assert result.returncode == 0, result.stderr
    assert "Start an interactive chat session with Motis" in result.stdout
    assert "--provider" in result.stdout
    assert "--resume" in result.stdout


def test_motis_chat_unconfigured_first_run_guidance(tmp_path: Path) -> None:
    motis_home = tmp_path / "motis-home"
    result = _run_motis("chat", "-q", "hello", env={"HERMES_HOME": str(motis_home)})
    combined_output = f"{result.stdout}\n{result.stderr}"

    assert result.returncode != 0
    assert "Motis isn't configured yet" in combined_output
    assert "motis setup" in combined_output


def test_motis_doctor_smoke(tmp_path: Path) -> None:
    motis_home = tmp_path / "motis-home"
    result = _run_motis("doctor", env={"HERMES_HOME": str(motis_home)})

    assert result.returncode == 0, result.stderr
    assert "Motis Doctor" in result.stdout
    assert "Configuration Files" in result.stdout
    assert ".env file missing" in result.stdout


def test_cli_module_import_does_not_require_fire(monkeypatch) -> None:
    upstream_root = REPO_ROOT / "services/upstream/hermes_agent"
    if str(upstream_root) not in sys.path:
        sys.path.insert(0, str(upstream_root))

    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "fire":
            raise ModuleNotFoundError("No module named 'fire'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop("cli", None)

    try:
        cli_module = importlib.import_module("cli")
        assert callable(cli_module.main)
    finally:
        sys.modules.pop("cli", None)
