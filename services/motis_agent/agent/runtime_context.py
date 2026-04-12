"""Process-local runtime context helpers for Hermes agent execution."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_current_agent: ContextVar[Any | None] = ContextVar("hermes_current_agent", default=None)


def set_current_agent(agent: Any) -> Token[Any | None]:
    """Bind the currently executing AIAgent for nested runtime helpers."""
    return _current_agent.set(agent)


def reset_current_agent(token: Token[Any | None]) -> None:
    """Restore the previous AIAgent binding."""
    _current_agent.reset(token)


def get_current_agent() -> Any | None:
    """Return the AIAgent currently executing a tool call, if any."""
    return _current_agent.get()
