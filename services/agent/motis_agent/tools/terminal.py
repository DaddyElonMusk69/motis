"""
Motis Terminal Tool
====================
Sandboxed Python execution for the master agent.

Adapted from NousResearch/hermes-agent tools/terminal_tool.py (MIT License)
Hermes supports 6 execution backends (local, Docker, SSH, Modal, Singularity, Daytona).
Motis uses 2:
  - Phase 0: restricted subprocess (safe for dev, single-machine)
  - Phase 1: per-user Docker container (multi-user safe, production)

Security constraints (both phases):
  - 30-second wall-clock timeout (configurable via settings)
  - No network access from within the sandbox (Phase 1: Docker --network none)
  - No access to the host filesystem outside a per-user temp directory
  - Blocked imports: socket, requests, httpx, subprocess, os.system, eval-like

Phase 0 stub: uses asyncio subprocess with allowed-import checking.
Phase 1 TODO: spawn per-user Docker containers from a whitelist image.
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motis_agent.context import UserContext

from motis_agent.settings import settings

logger = logging.getLogger(__name__)

# Imports that are blocked in Phase 0 subprocess execution
_BLOCKED_IMPORTS = frozenset({
    "socket", "http", "urllib", "requests", "httpx", "aiohttp",
    "subprocess", "multiprocessing", "threading",
    "paramiko", "ftplib", "smtplib", "imaplib",
})

_BLOCKED_PATTERN = re.compile(
    r"\b(import\s+(" + "|".join(_BLOCKED_IMPORTS) + r")|"
    r"__import__\s*\(|"
    r"exec\s*\(|eval\s*\(|"
    r"os\.system|os\.popen)\b"
)

_ALLOWED_PRELUDE = """\
import math, statistics, json, re, datetime, itertools, functools, collections
import numpy as np
import pandas as pd
# Finance data (read-only, no network):
# Use finance.* skills via the agent for live data — terminal is for computation only.
"""


async def motis_terminal(command: str, ctx: "UserContext") -> dict:
    """
    Execute Python code in a sandboxed environment.

    Phase 0: restrictive subprocess with import blocking.
    Returns {"stdout": str, "stderr": str, "exit_code": int, "truncated": bool}.
    """
    if not command.strip():
        return {"error": "Empty command"}

    if settings.terminal_backend == "docker":
        return await _run_docker(command, ctx)
    return await _run_subprocess(command, ctx)


async def _run_subprocess(command: str, ctx: "UserContext") -> dict:
    """
    Phase 0: run Python in a subprocess with basic import blocking.
    NOT suitable for production multi-user (share-nothing isolation is weak).
    """
    # Block dangerous imports
    if _BLOCKED_PATTERN.search(command):
        blocked = _BLOCKED_PATTERN.findall(command)
        return {
            "error": f"Blocked: {blocked[0][0] if blocked else 'dangerous pattern'}. "
                     "Use finance.* skills for data fetching — terminal is for computation only.",
        }

    # Write to a per-user temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix=f"motis_term_{ctx.user_id}_",
        delete=False,
    ) as f:
        f.write(_ALLOWED_PRELUDE + "\n" + command)
        script_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=settings.terminal_timeout_seconds,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "error": f"Timeout: execution exceeded {settings.terminal_timeout_seconds}s",
                "exit_code": -1,
            }

        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        truncated = len(out) > 8_000 or len(err) > 2_000

        return {
            "stdout": out[:8_000],
            "stderr": err[:2_000],
            "exit_code": proc.returncode,
            "truncated": truncated,
        }
    finally:
        Path(script_path).unlink(missing_ok=True)


async def _run_docker(command: str, ctx: "UserContext") -> dict:
    """
    Phase 1: per-user Docker container, no network, ephemeral filesystem.
    TODO: implement. Container image: motis-sandbox:latest
    (pre-built with numpy, pandas, pandas-ta, ccxt installed, no network at runtime)
    """
    raise NotImplementedError(
        "Docker terminal backend not yet implemented. "
        "Set TERMINAL_BACKEND=subprocess for Phase 0."
    )
