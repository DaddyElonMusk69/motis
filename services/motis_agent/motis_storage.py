#!/usr/bin/env python3
"""
Motis storage helpers for user-scoped local persistence.

Hermes historically treated local persistence as a single-user home-directory
cache. Motis needs the same local runtime to behave more like the platform
storage model: conversations and memories are explicitly scoped to a stable
user identity, even in standalone CLI mode.
"""

from __future__ import annotations

import re
from typing import Optional


def normalize_storage_source(source: Optional[str], fallback: str = "cli") -> str:
    """Normalize a storage source label."""
    normalized = str(source or fallback).strip().lower()
    return normalized or fallback


def _slug(value: Optional[str], fallback: str = "default") -> str:
    cleaned = re.sub(r"\s+", "-", str(value or "").strip().lower())
    cleaned = re.sub(r"[^a-z0-9._:-]+", "-", cleaned)
    cleaned = cleaned.strip("-")
    return cleaned or fallback


def _active_profile_name() -> str:
    try:
        from motis_cli.profiles import get_active_profile_name

        profile_name = get_active_profile_name()
        if profile_name:
            return str(profile_name)
    except Exception:
        pass
    return "default"


def resolve_motis_user_id(
    user_id: Optional[str] = None,
    source: Optional[str] = None,
) -> str:
    """Return a stable user identifier for Motis-style local storage."""
    explicit = str(user_id or "").strip()
    if explicit:
        return explicit

    normalized_source = normalize_storage_source(source)
    profile_name = _active_profile_name()
    return f"local:{normalized_source}:{_slug(profile_name)}"


def memory_type_for_target(target: str) -> str:
    """Map the built-in memory buckets onto Motis-style memory types."""
    if str(target).strip().lower() == "user":
        return "user_profile"
    return "agent_note"
