"""
Motis Builtin Skill Loader
============================
Loads markdown-based SKILL.md files from the builtin skills directory.

Builtin skills are instructional prompts (not callable tools) that the
master agent loads into its context window when it needs specialised
knowledge — like the operator-builder skill for constructing operators.

Design reference: docs/operators/02-contract-and-validation.md §How the Master Agent Builds an Operator
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Root directory for builtin skills (relative to this file)
_BUILTIN_SKILLS_DIR = Path(__file__).parent


def list_builtin_skills() -> list[dict[str, str]]:
    """
    Return metadata about all available builtin skills.
    Each has a name, description (first line of SKILL.md), and path.
    """
    skills = []
    for skill_dir in sorted(_BUILTIN_SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        # Extract description from first non-empty, non-heading line
        description = ""
        try:
            for line in skill_md.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith(">"):
                    description = stripped
                    break
        except Exception:
            pass

        skills.append({
            "name": skill_dir.name,
            "description": description,
            "path": str(skill_md),
        })

    return skills


def load_builtin_skill(skill_name: str) -> str | None:
    """
    Load and return the full content of a builtin SKILL.md file.
    Returns None if the skill doesn't exist.
    """
    skill_md = _BUILTIN_SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_md.exists():
        logger.warning("Builtin skill not found: %s", skill_name)
        return None

    try:
        content = skill_md.read_text(encoding="utf-8")
        logger.info("Loaded builtin skill: %s (%d chars)", skill_name, len(content))
        return content
    except Exception as exc:
        logger.error("Failed to load builtin skill %s: %s", skill_name, exc)
        return None


def get_operator_builder_context() -> str:
    """
    Convenience function: load the operator-builder skill content.
    Used by the system prompt builder when operators are part of the context.
    """
    content = load_builtin_skill("operator-builder")
    if content is None:
        return ""
    return content
