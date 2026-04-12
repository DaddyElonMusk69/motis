"""Shared constants for Motis.

Import-safe module with no dependencies — can be imported from anywhere
without risk of circular imports.
"""

import os
from pathlib import Path


def get_motis_home() -> Path:
    """Return the active Motis home directory.

    Resolution order:
    1. ``MOTIS_HOME`` (preferred)
    2. ``HERMES_HOME`` (compatibility)
    3. ``~/.motis`` default
    """
    return Path(
        os.getenv("MOTIS_HOME")
        or os.getenv("HERMES_HOME")
        or (Path.home() / ".motis")
    )


def get_hermes_home() -> Path:
    """Backward-compatible alias for older Hermes-named callers."""
    return get_motis_home()


def _motis_env_suffix(name: str) -> str:
    """Normalize a Motis/Hermes env var name to its shared suffix."""
    if name.startswith("MOTIS_"):
        return name[len("MOTIS_"):]
    if name.startswith("HERMES_"):
        return name[len("HERMES_"):]
    return name


def get_motis_env(name: str, default: str | None = None) -> str | None:
    """Return a Motis runtime env var, preferring Motis names over Hermes aliases."""
    suffix = _motis_env_suffix(name)
    for key in (f"MOTIS_{suffix}", f"HERMES_{suffix}"):
        if key in os.environ:
            return os.environ[key]
    return default


def set_motis_env(name: str, value: str, *, compatibility: bool = True) -> None:
    """Set a Motis env var and, by default, its Hermes compatibility alias."""
    suffix = _motis_env_suffix(name)
    text = str(value)
    os.environ[f"MOTIS_{suffix}"] = text
    if compatibility:
        os.environ[f"HERMES_{suffix}"] = text


def unset_motis_env(name: str, *, compatibility: bool = True) -> None:
    """Unset a Motis env var and, by default, its Hermes compatibility alias."""
    suffix = _motis_env_suffix(name)
    os.environ.pop(f"MOTIS_{suffix}", None)
    if compatibility:
        os.environ.pop(f"HERMES_{suffix}", None)


def get_optional_skills_dir(default: Path | None = None) -> Path:
    """Return the optional-skills directory, honoring package-manager wrappers.

    Packaged installs may ship ``optional-skills`` outside the Python package
    tree and expose it via ``MOTIS_OPTIONAL_SKILLS`` or the older
    ``HERMES_OPTIONAL_SKILLS`` compatibility variable.
    """
    override = (
        os.getenv("MOTIS_OPTIONAL_SKILLS", "").strip()
        or os.getenv("HERMES_OPTIONAL_SKILLS", "").strip()
    )
    if override:
        return Path(override)
    if default is not None:
        return default
    return get_motis_home() / "optional-skills"


def get_motis_dir(new_subpath: str, old_name: str) -> Path:
    """Resolve a Motis subdirectory with backward compatibility.

    New installs get the consolidated layout (e.g. ``cache/images``).
    Existing installs that already have the old path (e.g. ``image_cache``)
    keep using it — no migration required.

    Args:
        new_subpath: Preferred path relative to Motis home (e.g. ``"cache/images"``).
        old_name: Legacy path relative to Motis home (e.g. ``"image_cache"``).

    Returns:
        Absolute ``Path`` — old location if it exists on disk, otherwise the new one.
    """
    home = get_motis_home()
    old_path = home / old_name
    if old_path.exists():
        return old_path
    return home / new_subpath


def get_hermes_dir(new_subpath: str, old_name: str) -> Path:
    """Backward-compatible alias for older Hermes-named callers."""
    return get_motis_dir(new_subpath, old_name)


def display_motis_home() -> str:
    """Return a user-friendly display string for the current Motis home.

    Uses ``~/`` shorthand for readability::

        default:  ``~/.motis``
        profile:  ``~/.motis/profiles/coder``
        custom:   ``/opt/motis-custom``

    Use this in **user-facing** print/log messages instead of hardcoding
    the home path. For code that needs a real ``Path``, use
    :func:`get_motis_home` instead.
    """
    home = get_motis_home()
    try:
        return "~/" + str(home.relative_to(Path.home()))
    except ValueError:
        return str(home)


def display_hermes_home() -> str:
    """Backward-compatible alias for older Hermes-named callers."""
    return display_motis_home()


VALID_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")


def parse_reasoning_effort(effort: str) -> dict | None:
    """Parse a reasoning effort level into a config dict.

    Valid levels: "none", "minimal", "low", "medium", "high", "xhigh".
    Returns None when the input is empty or unrecognized (caller uses default).
    Returns {"enabled": False} for "none".
    Returns {"enabled": True, "effort": <level>} for valid effort levels.
    """
    if not effort or not effort.strip():
        return None
    effort = effort.strip().lower()
    if effort == "none":
        return {"enabled": False}
    if effort in VALID_REASONING_EFFORTS:
        return {"enabled": True, "effort": effort}
    return None


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"
OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE_URL}/chat/completions"

AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"
AI_GATEWAY_MODELS_URL = f"{AI_GATEWAY_BASE_URL}/models"
AI_GATEWAY_CHAT_URL = f"{AI_GATEWAY_BASE_URL}/chat/completions"
