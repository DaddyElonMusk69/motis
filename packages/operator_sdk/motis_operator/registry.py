"""
Motis Operator Registry
========================
Per-user operator registry backed by PostgreSQL.
Loaded into UserContext on every request.

Provides:
  - get(operator_id)           → OperatorModel | None
  - list(state_filter=None)    → list[OperatorModel]
  - get_context_block()        → str  (system prompt block for master agent)
  - create(spec)               → UUID
  - update_state(id, state)    → None
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from motis_shared.types import OperatorState

logger = logging.getLogger(__name__)


_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://motis:motis@localhost:5432/motis",
)

_engine = create_async_engine(
    _DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine,
    expire_on_commit=False,
    autoflush=False,
)


class OperatorRegistry:
    """
    Per-user view of the operator table.
    Instantiated by UserContext — one instance per request.
    """

    # Max operators to list in the system prompt context block
    _CONTEXT_BLOCK_LIMIT = 10

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    async def get(self, operator_id: UUID) -> dict | None:
        """Fetch a single operator by ID (must belong to this user)."""
        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT id, name, state, operator_type, asset_class, exchange,
                           cached_pnl_pct, cached_sharpe, cached_max_dd_pct,
                           risk_config, trigger_config, asset_universe,
                           created_at, updated_at
                    FROM operators
                    WHERE id = :id AND user_id = :user_id
                """),
                {"id": str(operator_id), "user_id": str(self.user_id)},
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None

    async def list(
        self,
        *,
        state_filter: str | None = None,
        operator_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List operators for this user, optionally filtered by state or type."""
        params: dict[str, Any] = {"user_id": str(self.user_id), "limit": limit}
        filters = ["user_id = :user_id"]

        if state_filter and state_filter != "all":
            filters.append("state = :state")
            params["state"] = state_filter

        if operator_type:
            filters.append("operator_type = :operator_type")
            params["operator_type"] = operator_type

        where = " AND ".join(filters)
        async with async_session() as session:
            result = await session.execute(
                text(f"""
                    SELECT id, name, state, operator_type, asset_class, exchange,
                           cached_pnl_pct, cached_sharpe, cached_max_dd_pct,
                           updated_at
                    FROM operators
                    WHERE {where}
                    ORDER BY updated_at DESC
                    LIMIT :limit
                """),
                params,
            )
            return [dict(row._mapping) for row in result.fetchall()]

    async def get_recent_logs(self, operator_id: UUID, *, limit: int = 20) -> list[dict]:
        """Return recent persisted run logs for a specific operator."""
        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT id, operator_id, node_name, level, message, data, created_at
                    FROM operator_run_logs
                    WHERE operator_id = :operator_id
                      AND operator_id IN (
                          SELECT id FROM operators WHERE id = :operator_id AND user_id = :user_id
                      )
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {
                    "operator_id": str(operator_id),
                    "user_id": str(self.user_id),
                    "limit": limit,
                },
            )
            return [dict(row._mapping) for row in result.fetchall()]

    async def create(self, spec: dict) -> UUID:
        """Insert a new operator record. Returns the new operator's UUID."""
        import uuid as _uuid
        op_id = _uuid.uuid4()
        async with async_session() as session:
            await session.execute(
                text("""
                    INSERT INTO operators (
                        id, user_id, name, description, state, operator_type,
                        asset_class, strategy_style, asset_universe, exchange,
                        risk_config, trigger_config, model_config_override,
                        graph_code, exchange_connection_id, allocated_capital_usd
                    ) VALUES (
                        :id, :user_id, :name, :description, :state, :operator_type,
                        :asset_class, :strategy_style, :asset_universe, :exchange,
                        :risk_config, :trigger_config, :model_config_override,
                        :graph_code, :exchange_connection_id, :allocated_capital_usd
                    )
                """),
                {
                    "id": str(op_id),
                    "user_id": str(self.user_id),
                    "name": spec.get("name", "Untitled Operator"),
                    "description": spec.get("description", ""),
                    "state": spec.get("state", OperatorState.DRAFT.value),
                    "operator_type": spec.get("type", "live_trade"),
                    "asset_class": spec.get("asset_class", "crypto_perp"),
                    "strategy_style": spec.get("strategy_style"),
                    "asset_universe": spec.get("asset_universe", []),
                    "exchange": spec.get("exchange"),
                    "risk_config": spec.get("risk_config", {}),
                    "trigger_config": spec.get("trigger_config", {}),
                    "model_config_override": spec.get("model_config_override"),
                    "graph_code": spec.get("graph_code"),
                    "exchange_connection_id": spec.get("exchange_connection_id"),
                    "allocated_capital_usd": spec.get("allocated_capital_usd"),
                },
            )
            await session.commit()
        return op_id

    async def update_state(self, operator_id: UUID, state: OperatorState) -> None:
        """Update an operator's state."""
        async with async_session() as session:
            await session.execute(
                text("""
                    UPDATE operators
                    SET state = :state, updated_at = now()
                    WHERE id = :id AND user_id = :user_id
                """),
                {
                    "id": str(operator_id),
                    "user_id": str(self.user_id),
                    "state": state.value,
                },
            )
            await session.commit()

    async def get_context_block(self) -> str:
        """
        Build an operator summary block for injection into the system prompt.
        Shows active operators (live, paper) first, then recent others.
        Returns empty string if the user has no operators.
        """
        operators = await self.list(limit=self._CONTEXT_BLOCK_LIMIT)
        if not operators:
            return ""

        lines = ["Operators:"]
        for op in operators:
            pnl_str = ""
            if op.get("cached_pnl_pct") is not None:
                sign = "+" if op["cached_pnl_pct"] >= 0 else ""
                pnl_str = f"  P&L: {sign}{op['cached_pnl_pct']:.1f}%"

            lines.append(
                f"  [{op['state'].upper()}] {op['name']} "
                f"({op['operator_type']} / {op['asset_class']}){pnl_str} "
                f"— id: {op['id']}"
            )

        return "\n".join(lines)
