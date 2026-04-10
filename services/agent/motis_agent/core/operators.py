"""
Motis Operator Service
======================

User-scoped operator interface for the Motis master agent.

This keeps operator management in the Motis runtime as a first-class local
primitive, peer to skills, while MCP remains reserved for remote guarded
execution and position access.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from motis_operator.registry import OperatorRegistry
from motis_shared.types import OperatorState


class OperatorService:
    """Local operator-layer facade used by the agent runtime."""

    def __init__(self, registry: OperatorRegistry) -> None:
        self._registry = registry

    async def create(self, *, name: str, operator_type: str, spec: dict[str, Any]) -> dict[str, Any]:
        create_spec = dict(spec)
        create_spec["name"] = name
        create_spec["type"] = operator_type

        operator_id = await self._registry.create(create_spec)
        operator = await self._registry.get(operator_id)

        return {
            "ok": True,
            "operator_id": str(operator_id),
            "operator": self._serialize_operator(operator),
        }

    async def list(self, *, state_filter: str = "all") -> dict[str, Any]:
        operators = await self._registry.list(state_filter=state_filter)
        return {
            "operators": [self._serialize_operator(item) for item in operators],
            "count": len(operators),
        }

    async def status(self, *, operator_id: UUID) -> dict[str, Any]:
        operator = await self._registry.get(operator_id)
        if not operator:
            raise ValueError("Operator not found")

        logs = await self._registry.get_recent_logs(operator_id, limit=20)
        return {
            "operator": self._serialize_operator(operator),
            "recent_logs": [self._serialize_log(log) for log in logs],
        }

    async def pause(self, *, operator_id: UUID, reason: str = "") -> dict[str, Any]:
        operator = await self._registry.get(operator_id)
        if not operator:
            raise ValueError("Operator not found")

        await self._registry.update_state(operator_id, OperatorState.PAUSED)
        updated = await self._registry.get(operator_id)

        return {
            "ok": True,
            "operator_id": str(operator_id),
            "state": OperatorState.PAUSED.value,
            "reason": reason,
            "operator": self._serialize_operator(updated),
        }

    async def archive(self, *, operator_id: UUID) -> dict[str, Any]:
        operator = await self._registry.get(operator_id)
        if not operator:
            raise ValueError("Operator not found")

        await self._registry.update_state(operator_id, OperatorState.ARCHIVED)
        updated = await self._registry.get(operator_id)

        return {
            "ok": True,
            "operator_id": str(operator_id),
            "state": OperatorState.ARCHIVED.value,
            "operator": self._serialize_operator(updated),
        }

    async def invoke(
        self,
        *,
        operator_id: UUID,
        input_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        operator = await self._registry.get(operator_id)
        if not operator:
            raise ValueError("Operator not found")

        return {
            "ok": False,
            "operator_id": str(operator_id),
            "status": "not_implemented",
            "message": (
                "Operator invocation stays in the Motis operator layer, "
                "but the local operator runtime bridge is not wired yet."
            ),
            "input": self._jsonable(input_payload or {}),
            "operator": self._serialize_operator(operator),
        }

    async def runtime_state(self, *, operator_id: UUID) -> dict[str, Any]:
        operator = await self._registry.get(operator_id)
        if not operator:
            raise ValueError("Operator not found")

        logs = await self._registry.get_recent_logs(operator_id, limit=50)
        return {
            "operator": self._serialize_operator(operator),
            "runtime_state": None,
            "recent_logs": [self._serialize_log(log) for log in logs],
            "state_backend": "not_wired",
            "message": (
                "Operator runtime state checkpoint retrieval is not wired yet. "
                "Returning persisted operator metadata and recent run logs."
            ),
        }

    def _serialize_operator(self, operator: dict[str, Any] | None) -> dict[str, Any] | None:
        if operator is None:
            return None
        return {key: self._jsonable(value) for key, value in operator.items()}

    def _serialize_log(self, log: dict[str, Any]) -> dict[str, Any]:
        return {key: self._jsonable(value) for key, value in log.items()}

    def _jsonable(self, value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [self._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._jsonable(item) for key, item in value.items()}
        return value
