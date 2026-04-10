"""
Motis Operator Registry
========================
Mode-aware operator registry that loads operators from filesystem (dev/standalone)
or PostgreSQL (platform mode).

In dev mode, operators are Python modules loaded from the filesystem at
``services/agent/motis_agent/operators/operators/``.  Each module must export
the operator contract: STATE, MANIFEST, build_graph().

In platform mode, operators are stored as graph_code TEXT in the operators
table, keyed by user_id.

Design reference: docs/operators/01-architecture-overview.md §The Operator Registry
Contract reference: docs/operators/02-contract-and-validation.md §The Operator Contract
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ── Operator contract validation ──────────────────────────────────────────────

_REQUIRED_EXPORTS = ("STATE", "MANIFEST", "build_graph")


def _is_valid_operator_module(module: ModuleType) -> bool:
    """Validate that a module exports the operator contract (STATE, MANIFEST, build_graph)."""
    return all(hasattr(module, attr) for attr in _REQUIRED_EXPORTS) and callable(
        getattr(module, "build_graph", None)
    )


def _is_valid_operator_namespace(ns: dict) -> bool:
    """Validate that an exec'd namespace contains the operator contract."""
    return all(k in ns for k in _REQUIRED_EXPORTS) and callable(ns.get("build_graph"))


# ── Filesystem operator loader ────────────────────────────────────────────────


def _load_module_from_path(filepath: Path) -> ModuleType | None:
    """Import a Python module from an absolute path without polluting sys.modules permanently."""
    # Derive module name from folder structure: operators/<category>/<name>/operator.py
    op_dir_name = filepath.parent.name
    category_name = filepath.parent.parent.name
    module_name = f"motis_agent.operators.{category_name}.{op_dir_name}.operator"
    try:
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            logger.warning("Cannot build import spec for %s", filepath)
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        logger.error("Failed to load operator module %s: %s", filepath, exc, exc_info=True)
        return None


class _LoadedOperator:
    """A thin wrapper around a loaded operator module (filesystem or exec'd)."""

    __slots__ = ("module", "manifest", "state_type", "operator_id", "source")

    def __init__(self, module: ModuleType | dict, *, operator_id: str, source: str):
        if isinstance(module, dict):
            self.manifest = module["MANIFEST"]
            self.state_type = module["STATE"]
            self.module = module
        else:
            self.manifest = module.MANIFEST
            self.state_type = module.STATE
            self.module = module
        self.operator_id = operator_id
        self.source = source  # "filesystem" | "database"

    def build_graph(self):
        if isinstance(self.module, dict):
            return self.module["build_graph"]()
        return self.module.build_graph()

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a dict suitable for the operator context block and serialisation."""
        manifest = self.manifest
        return {
            "id": self.operator_id,
            "name": manifest.get("name", "unnamed"),
            "state": manifest.get("_runtime_state", "draft"),
            "operator_type": manifest.get("type", "unknown"),
            "asset_class": manifest.get("asset_class", ""),
            "exchange": manifest.get("exchange", ""),
            "asset_universe": manifest.get("asset_universe", []),
            "risk": manifest.get("risk", {}),
            "trigger": manifest.get("trigger", {}),
            "nodes": [n.get("name") for n in manifest.get("nodes", [])],
            "source": self.source,
        }


# ── Registry ──────────────────────────────────────────────────────────────────


class OperatorRegistry:
    """
    Per-user, mode-aware operator registry.

    Instantiated by UserContext — one instance per request.
    In dev mode, operators are loaded from the filesystem at ``operators_path``.
    In platform mode, operators are loaded from PostgreSQL (existing behaviour).

    Design reference: docs/operators/01-architecture-overview.md §The Operator Registry
    """

    # Max operators to show in the system prompt
    _CONTEXT_BLOCK_LIMIT = 10

    def __init__(
        self,
        user_id: UUID,
        *,
        runtime_mode: str = "dev",
        operators_path: str = "",
    ) -> None:
        self.user_id = user_id
        self.runtime_mode = runtime_mode
        self.operators_path = operators_path

        # Loaded operators cache (populated lazily)
        self._operators: dict[str, _LoadedOperator] | None = None

    # ── Loading ───────────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> dict[str, _LoadedOperator]:
        """Lazy-load operators on first access."""
        if self._operators is not None:
            return self._operators

        self._operators = {}

        if self.runtime_mode in ("dev", "standalone"):
            self._load_from_filesystem()
        # Platform mode: operators loaded on-demand via get() / list() from DB
        # (no eager loading — could be thousands of operators per user)

        return self._operators

    def _load_from_filesystem(self) -> None:
        """
        Scan the operators directory for operator folders.

        Convention: each operator is a folder containing ``operator.py``
        that exports the contract (STATE, MANIFEST, build_graph).

        Scans three subdirectories:
          - examples/  — reference implementations
          - builtin/   — production-ready (ported from vibe trading)
          - user/      — agent-generated at runtime

        Skips folders starting with ``_`` or ``.``.
        """
        if not self.operators_path:
            logger.debug("No operators_path configured — skipping filesystem load")
            return

        operators_dir = Path(self.operators_path)
        if not operators_dir.is_dir():
            logger.info(
                "Operators directory does not exist, creating: %s", operators_dir
            )
            operators_dir.mkdir(parents=True, exist_ok=True)
            return

        # Scan each category subdirectory
        for category in ("examples", "builtin", "user"):
            category_dir = operators_dir / category
            if not category_dir.is_dir():
                continue

            for op_dir in sorted(category_dir.iterdir()):
                if not op_dir.is_dir():
                    continue
                if op_dir.name.startswith(("_", ".")):
                    continue

                entry_point = op_dir / "operator.py"
                if not entry_point.exists():
                    logger.debug("Skipping %s — no operator.py", op_dir.name)
                    continue

                module = _load_module_from_path(entry_point)
                if module is None:
                    continue

                if not _is_valid_operator_module(module):
                    logger.warning(
                        "Skipping %s/%s — missing operator contract (STATE, MANIFEST, build_graph)",
                        category,
                        op_dir.name,
                    )
                    continue

                manifest = module.MANIFEST
                op_name = manifest.get("name", op_dir.name)
                op_id = f"{category}-{op_dir.name}"

                self._operators[op_id] = _LoadedOperator(
                    module=module, operator_id=op_id, source="filesystem"
                )
                logger.info(
                    "Loaded operator: %s (%s) from %s/%s/operator.py",
                    op_name, op_id, category, op_dir.name,
                )

    # ── Public API (used by OperatorService + system prompt) ──────────────────

    async def get(self, operator_id: UUID | str) -> dict | None:
        """Fetch a single operator by ID."""
        op_id_str = str(operator_id)

        if self.runtime_mode in ("dev", "standalone"):
            ops = self._ensure_loaded()
            loaded = ops.get(op_id_str)
            return loaded.to_summary_dict() if loaded else None

        # Platform mode: fall through to DB query
        return await self._db_get(op_id_str)

    async def list(
        self,
        *,
        state_filter: str | None = None,
        operator_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List operators for this user."""
        if self.runtime_mode in ("dev", "standalone"):
            ops = self._ensure_loaded()
            results = [op.to_summary_dict() for op in ops.values()]

            if state_filter and state_filter != "all":
                results = [r for r in results if r["state"] == state_filter]
            if operator_type:
                results = [r for r in results if r["operator_type"] == operator_type]

            return results[:limit]

        # Platform mode: DB query
        return await self._db_list(state_filter=state_filter, limit=limit)

    async def get_loaded_operator(self, operator_id: str) -> _LoadedOperator | None:
        """Return the _LoadedOperator for invocation (graph building)."""
        ops = self._ensure_loaded()
        return ops.get(operator_id)

    async def get_recent_logs(self, operator_id: UUID | str, *, limit: int = 20) -> list[dict]:
        """Return recent run logs. Filesystem mode: empty (no persistence yet)."""
        if self.runtime_mode in ("dev", "standalone"):
            return []  # TODO: read from local SQLite state.db
        return await self._db_get_logs(str(operator_id), limit=limit)

    async def create(self, spec: dict) -> UUID:
        """Create a new operator. In dev mode, creates a folder with operator.py."""
        if self.runtime_mode in ("dev", "standalone"):
            return await self._fs_create(spec)
        return await self._db_create(spec)

    async def update_state(self, operator_id: UUID | str, state: Any) -> None:
        """Update operator state. Dev mode: updates the in-memory manifest."""
        op_id_str = str(operator_id)

        if self.runtime_mode in ("dev", "standalone"):
            ops = self._ensure_loaded()
            loaded = ops.get(op_id_str)
            if loaded:
                loaded.manifest["_runtime_state"] = state.value if hasattr(state, "value") else str(state)
            return

        await self._db_update_state(op_id_str, state)

    async def get_context_block(self) -> str:
        """
        Build an operator summary block for injection into the system prompt.
        Shows loaded operators with their metadata.
        Returns empty string if no operators are loaded.

        Design reference: docs/operators/03-sdk-and-execution.md §Operator Visibility to the Master Agent
        """
        operators = await self.list(limit=self._CONTEXT_BLOCK_LIMIT)
        if not operators:
            return ""

        lines = ["Operators:"]
        for op in operators:
            state = op.get("state", "draft").upper()
            name = op.get("name", "unnamed")
            op_type = op.get("operator_type", "")
            asset_class = op.get("asset_class", "")
            exchange = op.get("exchange", "")
            nodes = op.get("nodes", [])
            risk = op.get("risk", {})

            detail_parts = []
            if op_type:
                detail_parts.append(op_type)
            if asset_class:
                detail_parts.append(asset_class)
            if exchange:
                detail_parts.append(exchange)
            detail = " / ".join(detail_parts)

            line = f"  [{state}] {name} ({detail})  id: {op['id']}"
            if nodes:
                line += f"  nodes: {', '.join(nodes)}"
            if risk.get("risk_per_trade_pct"):
                line += f"  risk/trade: {risk['risk_per_trade_pct']}%"

            lines.append(line)

        return "\n".join(lines)

    # ── Filesystem create ─────────────────────────────────────────────────────

    async def _fs_create(self, spec: dict) -> UUID:
        """
        Create a new operator as a folder with operator.py in the user/ subdirectory.
        Agent-generated operators always go to operators/user/<name>/operator.py.
        """
        op_id = uuid4()
        graph_code = spec.get("graph_code", "")
        if not graph_code:
            logger.warning("operator_create called without graph_code — creating empty stub")
            name = spec.get("name", "Untitled")
            graph_code = f'"""\n{name}\nGenerated by Motis agent. Edit to implement.\n"""\n\nSTATE = dict\nMANIFEST = {{"name": "{name}", "type": "{spec.get("type", "paper_trade")}"}}\n\ndef build_graph():\n    raise NotImplementedError("Operator not implemented yet")\n'

        # Sanitize name to a valid directory name
        safe_name = spec.get("name", "untitled").lower().replace(" ", "_").replace("-", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")

        # Agent-generated operators go to user/
        op_dir = Path(self.operators_path) / "user" / safe_name
        op_dir.mkdir(parents=True, exist_ok=True)

        filepath = op_dir / "operator.py"
        filepath.write_text(graph_code, encoding="utf-8")
        logger.info("Created operator: %s", filepath)

        # Reload registry to pick up the new operator
        self._operators = None
        self._ensure_loaded()

        return op_id

    # ── Database methods (platform mode — preserved from original) ────────────

    async def _db_get(self, operator_id: str) -> dict | None:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        engine = self._get_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

        async with session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, name, state, operator_type, asset_class, exchange,
                           cached_pnl_pct, cached_sharpe, cached_max_dd_pct,
                           risk_config, trigger_config, asset_universe,
                           created_at, updated_at
                    FROM operators
                    WHERE id = :id AND user_id = :user_id
                """),
                {"id": operator_id, "user_id": str(self.user_id)},
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None

    async def _db_list(self, *, state_filter: str | None = None, limit: int = 50) -> list[dict]:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker

        engine = self._get_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

        params: dict[str, Any] = {"user_id": str(self.user_id), "limit": limit}
        filters = ["user_id = :user_id"]

        if state_filter and state_filter != "all":
            filters.append("state = :state")
            params["state"] = state_filter

        where = " AND ".join(filters)
        async with session_factory() as session:
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

    async def _db_get_logs(self, operator_id: str, *, limit: int = 20) -> list[dict]:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker

        engine = self._get_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

        async with session_factory() as session:
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
                    "operator_id": operator_id,
                    "user_id": str(self.user_id),
                    "limit": limit,
                },
            )
            return [dict(row._mapping) for row in result.fetchall()]

    async def _db_create(self, spec: dict) -> UUID:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker
        import uuid as _uuid

        engine = self._get_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

        from motis_shared.types import OperatorState

        op_id = _uuid.uuid4()
        async with session_factory() as session:
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

    async def _db_update_state(self, operator_id: str, state: Any) -> None:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker

        engine = self._get_engine()
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

        async with session_factory() as session:
            await session.execute(
                text("""
                    UPDATE operators
                    SET state = :state, updated_at = now()
                    WHERE id = :id AND user_id = :user_id
                """),
                {
                    "id": operator_id,
                    "user_id": str(self.user_id),
                    "state": state.value if hasattr(state, "value") else str(state),
                },
            )
            await session.commit()

    def _get_engine(self):
        """Lazy engine creation for platform mode (only when DB is needed)."""
        if not hasattr(self, "_engine"):
            from sqlalchemy.ext.asyncio import create_async_engine

            db_url = os.environ.get(
                "DATABASE_URL",
                "postgresql+asyncpg://motis:motis@localhost:5432/motis",
            )
            self._engine = create_async_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,
            )
        return self._engine
