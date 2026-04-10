"""
Motis Skill Registry
====================

Motis uses "skills" to mean callable domain capabilities exposed as model tools.
This is different from the upstream procedural SKILL.md system, which we may port
later under a different name.

Current scope:
- Finance/data/research/reporting callable skills from `motis_agent.skills.finance`

Future scope:
- User-defined callable skills stored in the platform DB
- Operator-scoped skill packs
- A separate procedural playbook system derived from the upstream markdown skills
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from motis_agent.skills.finance import FINANCE_SKILL_DEFINITIONS


@dataclass(frozen=True)
class SkillMetadata:
    """Lightweight metadata for a callable Motis skill."""

    name: str
    description: str
    source: str = "finance"


class SkillRegistry:
    """
    Per-user registry of callable Motis skills.

    The current implementation is intentionally small: it provides a stable
    Motis-owned interface over the callable finance skills already in the repo.
    This lets the runtime depend on a Motis registry abstraction now, while we
    decide how future user-defined skills and procedural playbooks should fit.
    """

    def __init__(self, user_id: UUID):
        self.user_id = user_id

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return OpenAI tool schemas for callable skills available to this user."""
        return [dict(tool) for tool in FINANCE_SKILL_DEFINITIONS]

    def get_tool_names(self) -> set[str]:
        """Return the callable skill tool names."""
        return {
            tool["function"]["name"]
            for tool in FINANCE_SKILL_DEFINITIONS
            if tool.get("type") == "function" and "function" in tool
        }

    def has_tool(self, tool_name: str) -> bool:
        """Check whether a callable skill exists."""
        return tool_name in self.get_tool_names()

    def list_skills(self) -> list[SkillMetadata]:
        """Return a compact metadata list for prompt-building or UI use."""
        return [
            SkillMetadata(
                name=tool["function"]["name"],
                description=tool["function"].get("description", ""),
            )
            for tool in FINANCE_SKILL_DEFINITIONS
            if tool.get("type") == "function" and "function" in tool
        ]

