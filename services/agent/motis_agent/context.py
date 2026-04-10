from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from fastapi import Header, HTTPException

if TYPE_CHECKING:
    from motis_agent.core.memory import MemoryStore
    from motis_agent.core.skills import SkillRegistry
    from motis_operator.registry import OperatorRegistry


@dataclass
class ModelConfig:
    """
    Per-user model configuration (BYOM — Bring Your Own Model).

    The master agent and each Operator can have independent model configs.
    reference_models: additional models used by the MixtureOfAgents tool.
    If empty, the primary model is used for all MoA reference calls.
    """
    base_url: str
    api_key: str
    model: str
    reference_models: list[str] = field(default_factory=list)


@dataclass
class UserContext:
    """
    Per-user scoped context. Resolved on every request from JWT headers.
    All resources (memory, skills, operators) are scoped to user_id.

    Adapted from the upstream Hermes single-user filesystem design:
    - Hermes: state lives on disk at ~/.hermes/ (single user, single process)
    - Motis: state lives in PostgreSQL keyed by user_id (N users, N processes)

    Used by: MotisAgentLoop, MotisToolRouter, SubagentRunner, MoA tool,
    MemoryStore, OperatorRegistry, SkillRegistry.
    """

    user_id: UUID
    email: str
    model_config: ModelConfig
    conversation_id: UUID = field(default_factory=uuid4)

    # Lazy-initialised by __post_init__ — never set directly
    memory: "MemoryStore" = field(init=False)
    skill_registry: "SkillRegistry" = field(init=False)
    operator_registry: "OperatorRegistry" = field(init=False)

    # Populated lazily — cached after first DB check
    _has_connected_exchange: Optional[bool] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        from motis_agent.core.memory import MemoryStore
        from motis_agent.core.skills import SkillRegistry
        from motis_operator.registry import OperatorRegistry

        self.memory = MemoryStore(user_id=self.user_id)
        self.skill_registry = SkillRegistry(user_id=self.user_id)
        self.operator_registry = OperatorRegistry(user_id=self.user_id)

    @property
    def has_connected_exchange(self) -> bool:
        """
        Returns True if the user has at least one exchange API key configured.
        Determines whether execution tools (execute_live_trade, get_positions)
        are included in the tool registry.

        TODO: replace synchronous attribute with async DB check in server.py
        (cache result on context after resolving from DB at request time).
        """
        if self._has_connected_exchange is None:
            # Stub: assume no connected exchange until DB check is implemented.
            # server.py will set this during context resolution once the
            # exchange_keys table is queryable.
            return False
        return self._has_connected_exchange


async def get_user_context(
    x_user_id: str = Header(...),
    x_user_email: str = Header(...),
    x_model_base_url: str = Header(...),
    x_model_api_key: str = Header(...),
    x_model_name: str = Header(...),
    x_model_reference_models: str = Header(default=""),
    x_conversation_id: str = Header(default=""),
) -> UserContext:
    """
    FastAPI dependency. The platform gateway validates the JWT and injects
    user context as trusted internal headers (X-User-Id, X-Model-*, etc.).

    The platform gateway is the only service that talks to the DB for auth.
    This service receives pre-validated headers and trusts them.

    x_model_reference_models: comma-separated list of extra models for MoA.
    x_conversation_id: UUID of the current conversation (for memory scoping).
    """
    try:
        user_id = UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id")

    conversation_id: UUID
    if x_conversation_id:
        try:
            conversation_id = UUID(x_conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Conversation-Id")
    else:
        conversation_id = uuid4()

    reference_models = (
        [m.strip() for m in x_model_reference_models.split(",") if m.strip()]
        if x_model_reference_models
        else []
    )

    model_config = ModelConfig(
        base_url=x_model_base_url,
        api_key=x_model_api_key,
        model=x_model_name,
        reference_models=reference_models,
    )

    return UserContext(
        user_id=user_id,
        email=x_user_email,
        model_config=model_config,
        conversation_id=conversation_id,
    )

