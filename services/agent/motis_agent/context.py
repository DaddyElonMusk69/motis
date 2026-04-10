from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from motis_agent.core.memory import MemoryStore
    from motis_agent.core.skills import SkillRegistry
    from motis_operator.registry import OperatorRegistry


@dataclass
class UserContext:
    """
    Per-user scoped context. Resolved on every request from JWT.
    Wraps all resources that are isolated per user.

    This is the multi-user adaptation of Hermes's single-user filesystem state.
    Instead of ~/.hermes/, everything lives in the DB scoped to user_id.
    """

    user_id: UUID
    email: str
    model_base_url: str          # User's BYOM config (or platform default)
    model_api_key: str
    model_name: str

    memory: "MemoryStore" = field(init=False)
    skill_registry: "SkillRegistry" = field(init=False)
    operator_registry: "OperatorRegistry" = field(init=False)

    def __post_init__(self):
        from motis_agent.core.memory import MemoryStore
        from motis_agent.core.skills import SkillRegistry
        from motis_operator.registry import OperatorRegistry

        self.memory = MemoryStore(user_id=self.user_id)
        self.skill_registry = SkillRegistry(user_id=self.user_id)
        self.operator_registry = OperatorRegistry(user_id=self.user_id)


async def get_user_context(
    x_user_id: str = Header(...),
    x_user_email: str = Header(...),
    x_model_base_url: str = Header(...),
    x_model_api_key: str = Header(...),
    x_model_name: str = Header(...),
) -> UserContext:
    """
    FastAPI dependency. The platform gateway validates the JWT and forwards
    user context as trusted internal headers to this service.
    """
    try:
        user_id = UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    return UserContext(
        user_id=user_id,
        email=x_user_email,
        model_base_url=x_model_base_url,
        model_api_key=x_model_api_key,
        model_name=x_model_name,
    )
