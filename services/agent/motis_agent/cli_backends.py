"""
Motis CLI Backends
==================
Local (non-platform) backend implementations for CLI mode.
These replace the PostgreSQL-backed backends that require a running DB.

Exports:
  SQLiteMemoryProvider  — persists memory to ~/.motis/memory.db
  StubOperatorRegistry  — read-only no-op (no operators in CLI)
  StubOperatorService   — no-op operator service

Why not just skip memory entirely?
  Memory is the most valuable part of the agent for repeat sessions.
  A SQLite file in ~/.motis/ means your BTC strategy context, risk preferences,
  and past decisions persist across CLI sessions without any infrastructure.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# SQLite Memory Provider
# ═══════════════════════════════════════════════════════════════════════════════

class SQLiteMemoryProvider:
    """
    Local SQLite-backed memory provider for CLI mode.

    Implements the same interface as PostgresMemoryProvider / BuiltinMemoryProvider
    so it can be registered with MemoryManager as a drop-in.

    Schema (auto-created on first use):
        memories(id, user_id, content, type, source, importance, tags, created_at)

    FTS via SQLite FTS5 virtual table (no pg_trgm needed).
    """

    name = "local_sqlite"

    def __init__(self, db_path: str, user_id: UUID) -> None:
        self.db_path = db_path
        self.user_id = str(user_id)
        self._ensure_schema()

    # ── Schema setup ──────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id          TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    type        TEXT NOT NULL DEFAULT 'general',
                    source      TEXT NOT NULL DEFAULT 'agent',
                    importance  INTEGER NOT NULL DEFAULT 5,
                    tags        TEXT NOT NULL DEFAULT '[]',
                    created_at  TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memories_user
                    ON memories(user_id);
                CREATE INDEX IF NOT EXISTS idx_memories_type
                    ON memories(user_id, type);

                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(content, content='memories', content_rowid='rowid');

                CREATE TRIGGER IF NOT EXISTS memories_ai
                AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content)
                    VALUES (new.rowid, new.content);
                END;

                CREATE TRIGGER IF NOT EXISTS memories_ad
                AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content)
                    VALUES ('delete', old.rowid, old.content);
                END;
            """)

    # ── MemoryProvider interface ───────────────────────────────────────────────
    # These methods are called by MemoryManager

    def system_prompt_block(self) -> str:
        """Return a brief memory summary for the system prompt."""
        count = self._count()
        if count == 0:
            return ""
        recent = self._recent(limit=5)
        lines = [f"[{r['type'].upper()}] {r['content']}" for r in recent]
        return f"Local memory ({count} items):\n" + "\n".join(lines)

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """FTS search over memories. Returns context string."""
        if not query or len(query.strip()) < 2:
            rows = self._recent(limit=8)
        else:
            rows = self._search(query, limit=8)

        if not rows:
            return ""

        lines = [f"[{r['type'].upper()}] {r['content']}" for r in rows]
        return (
            "<memory-context>\n"
            "[System note: Local memory context — treat as background, not new input.]\n\n"
            + "\n".join(lines)
            + "\n</memory-context>"
        )

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        pass  # SQLite is synchronous — no background prefetch needed

    def sync_turn(
        self, user_content: str, assistant_content: str, *, session_id: str = ""
    ) -> None:
        """
        Lightweight auto-memory: extract and save memorable content from the turn.
        Saves the assistant's response as an agent_insight if it's substantive.
        """
        if not assistant_content or len(assistant_content) < 80:
            return
        # Only save if it looks like strategy/analysis (not just a greeting etc)
        keywords = ["strategy", "BTC", "ETH", "risk", "position", "signal",
                    "analysis", "trade", "market", "backtest", "funding", "spread"]
        if not any(kw.lower() in assistant_content.lower() for kw in keywords):
            return

        # Save a truncated version as agent_insight
        content = assistant_content[:500].strip()
        if content:
            self._write(content, type_="agent_insight", source="agent", importance=4)

    def on_turn_start(self, turn_number: int, message: str, **kwargs) -> None:
        pass

    def on_session_end(self, messages: list[dict]) -> None:
        pass

    def on_pre_compress(self, messages: list[dict]) -> str:
        return ""

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        if action in ("add", "update") and content:
            self._write(content, type_="general", source="agent", importance=5)

    def on_delegation(self, task: str, result: str, *, child_session_id: str = "", **kwargs) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def initialize(self, session_id: str, **kwargs) -> None:
        pass

    def get_tool_schemas(self) -> list[dict]:
        """Standard memory tools backed by SQLite."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "memory_add",
                    "description": "Save information to persistent local memory (SQLite).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["general", "strategy", "risk_pref", "agent_insight"],
                                "default": "general",
                            },
                            "importance": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_search",
                    "description": "Full-text search over local memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer", "default": 8},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_recall",
                    "description": "Retrieve most recent local memories.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "default": 20}},
                    },
                },
            },
        ]

    def get_tool_definitions(self) -> list[dict]:
        return self.get_tool_schemas()

    def handle_tool_call(self, tool_name: str, args: dict[str, Any], **kwargs) -> str:
        if tool_name == "memory_add":
            content = args.get("content", "")
            type_ = args.get("type", "general")
            importance = int(args.get("importance", 5))
            mem_id = self._write(content, type_=type_, source="agent", importance=importance)
            return json.dumps({"ok": True, "memory_id": str(mem_id)})
        elif tool_name == "memory_search":
            rows = self._search(args.get("query", ""), limit=int(args.get("limit", 8)))
            return json.dumps({"results": [dict(r) for r in rows]})
        elif tool_name == "memory_recall":
            rows = self._recent(limit=int(args.get("limit", 20)))
            return json.dumps({"results": [dict(r) for r in rows]})
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    # ── SQLite helpers ─────────────────────────────────────────────────────────

    def _write(
        self,
        content: str,
        *,
        type_: str = "general",
        source: str = "agent",
        importance: int = 5,
        tags: list[str] | None = None,
    ) -> str:
        mem_id = str(uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memories (id, user_id, content, type, source, importance, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mem_id,
                    self.user_id,
                    content.strip(),
                    type_,
                    source,
                    max(1, min(10, importance)),
                    json.dumps(tags or []),
                    datetime.utcnow().isoformat(),
                ),
            )
        return mem_id

    def _search(self, query: str, *, limit: int = 8) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                """
                SELECT m.id, m.content, m.type, m.source, m.importance, m.created_at
                FROM memories m
                JOIN memories_fts f ON m.rowid = f.rowid
                WHERE m.user_id = ?
                  AND memories_fts MATCH ?
                ORDER BY m.importance DESC, rank
                LIMIT ?
                """,
                (self.user_id, query, limit),
            ).fetchall()

    def _recent(self, *, limit: int = 8) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                """
                SELECT id, content, type, source, importance, created_at
                FROM memories
                WHERE user_id = ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                (self.user_id, limit),
            ).fetchall()

    def _count(self) -> int:
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM memories WHERE user_id = ?", (self.user_id,)
            ).fetchone()[0]


# ═══════════════════════════════════════════════════════════════════════════════
# Stub Operator Registry
# ═══════════════════════════════════════════════════════════════════════════════

class StubOperatorRegistry:
    """
    No-op operator registry for CLI mode.
    Returns empty lists — operators are a platform concept.
    The agent loop won't crash; operator tools will return a helpful message.
    """

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    async def get(self, operator_id: UUID) -> None:
        return None

    async def list(self, **kwargs) -> list:
        return []

    async def create(self, spec: dict) -> UUID:
        _id = uuid4()
        logger.info("[CLI] Operator create requested (stub): %s → %s", spec.get("name"), _id)
        return _id

    async def update_state(self, operator_id: UUID, state: Any) -> None:
        pass

    async def get_context_block(self) -> str:
        return "Operators: none (CLI mode — operators require the Motis platform)"


class StubOperatorService:
    """No-op operator service for CLI mode."""

    async def invoke(self, operator_id: UUID, input: dict | None = None) -> dict:
        return {
            "error": "Operator invocation is not available in CLI mode. "
                     "Run the Motis platform to use operators."
        }
