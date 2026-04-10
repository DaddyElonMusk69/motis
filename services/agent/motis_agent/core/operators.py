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

from motis_agent.core.operator_registry import OperatorRegistry
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
        """
        Run an operator's graph synchronously and return the result.

        In dev/standalone mode, loads the operator from the filesystem via
        the registry, builds its LangGraph graph, and invokes it.

        Design reference: docs/operators/03-sdk-and-execution.md §Runtime Execution
        """
        # Try to get the loaded operator (filesystem or DB-backed)
        loaded = await self._registry.get_loaded_operator(str(operator_id))
        if loaded is None:
            # Fall back to the simple dict lookup
            operator = await self._registry.get(operator_id)
            if not operator:
                raise ValueError(f"Operator not found: {operator_id}")
            return {
                "ok": False,
                "operator_id": str(operator_id),
                "status": "not_runnable",
                "message": (
                    "Operator found but cannot be invoked — it may be a platform "
                    "operator and the local runtime bridge is not wired yet."
                ),
                "operator": self._serialize_operator(operator),
            }

        # Build the graph
        try:
            graph = loaded.build_graph()
        except Exception as exc:
            return {
                "ok": False,
                "operator_id": str(operator_id),
                "status": "build_failed",
                "message": f"Failed to build operator graph: {exc}",
            }

        # Invoke the graph
        try:
            initial_state = dict(input_payload or {})
            if hasattr(graph, "ainvoke"):
                # LangGraph compiled graph
                result = await graph.ainvoke(initial_state)
            elif callable(graph):
                # Fallback sequential runner
                result = await graph(initial_state)
            else:
                return {
                    "ok": False,
                    "operator_id": str(operator_id),
                    "status": "invalid_graph",
                    "message": "build_graph() returned a non-callable, non-graph object.",
                }
        except Exception as exc:
            return {
                "ok": False,
                "operator_id": str(operator_id),
                "status": "execution_failed",
                "message": f"Operator execution failed: {exc}",
            }

        return {
            "ok": True,
            "operator_id": str(operator_id),
            "status": "completed",
            "result": self._jsonable(result),
            "operator": loaded.to_summary_dict(),
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
