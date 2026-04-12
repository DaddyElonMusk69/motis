#!/usr/bin/env python3
"""
SQLite state store for Motis.

The standalone runtime exposes a compatibility-oriented ``SessionDB`` API, but
its active storage model is Motis-shaped:

- conversations
- conversation_messages
- agent_memories

Legacy Hermes ``sessions`` / ``messages`` tables are migration inputs only and
are no longer the active write path.
"""

import json
import logging
import random
import re
import sqlite3
import threading
import time
from pathlib import Path
from motis_constants import get_motis_home
from motis_storage import normalize_storage_source, resolve_motis_user_id
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

def get_default_db_path() -> Path:
    """Return the active profile-scoped SQLite path."""
    return get_motis_home() / "state.db"


DEFAULT_DB_PATH = get_default_db_path()

SCHEMA_VERSION = 8

BASE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""

MOTIS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT,
    source TEXT NOT NULL,
    model TEXT,
    model_config TEXT,
    system_prompt TEXT,
    parent_conversation_id TEXT,
    started_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    ended_at REAL,
    end_reason TEXT,
    message_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0,
    billing_provider TEXT,
    billing_base_url TEXT,
    billing_mode TEXT,
    estimated_cost_usd REAL,
    actual_cost_usd REAL,
    cost_status TEXT,
    cost_source TEXT,
    pricing_version TEXT,
    FOREIGN KEY (parent_conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id INTEGER PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT,
    tool_call_id TEXT,
    tool_calls TEXT,
    tool_name TEXT,
    created_at REAL NOT NULL,
    sequence INTEGER NOT NULL,
    token_count INTEGER,
    finish_reason TEXT,
    reasoning TEXT,
    reasoning_details TEXT,
    codex_reasoning_items TEXT
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_source ON conversations(source);
CREATE INDEX IF NOT EXISTS idx_conversations_parent ON conversations(parent_conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_started ON conversations(started_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_title_unique
    ON conversations(title) WHERE title IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation
    ON conversation_messages(conversation_id, sequence);

CREATE TABLE IF NOT EXISTS agent_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    target TEXT NOT NULL,
    content TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'general',
    tags TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'builtin',
    importance INTEGER NOT NULL DEFAULT 5,
    position INTEGER NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(user_id, target, position),
    UNIQUE(user_id, target, content)
);

CREATE INDEX IF NOT EXISTS idx_agent_memories_user_target
    ON agent_memories(user_id, target, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_memories_type
    ON agent_memories(user_id, type);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content=messages,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_update AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
"""

CONVERSATION_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS conversation_messages_fts USING fts5(
    content,
    content=conversation_messages,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS conversation_messages_fts_insert
AFTER INSERT ON conversation_messages BEGIN
    INSERT INTO conversation_messages_fts(rowid, content)
    VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS conversation_messages_fts_delete
AFTER DELETE ON conversation_messages BEGIN
    INSERT INTO conversation_messages_fts(conversation_messages_fts, rowid, content)
    VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS conversation_messages_fts_update
AFTER UPDATE ON conversation_messages BEGIN
    INSERT INTO conversation_messages_fts(conversation_messages_fts, rowid, content)
    VALUES('delete', old.id, old.content);
    INSERT INTO conversation_messages_fts(rowid, content)
    VALUES (new.id, new.content);
END;
"""

MEMORY_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS agent_memories_fts USING fts5(
    content,
    content=agent_memories,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS agent_memories_fts_insert
AFTER INSERT ON agent_memories BEGIN
    INSERT INTO agent_memories_fts(rowid, content)
    VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS agent_memories_fts_delete
AFTER DELETE ON agent_memories BEGIN
    INSERT INTO agent_memories_fts(agent_memories_fts, rowid, content)
    VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS agent_memories_fts_update
AFTER UPDATE OF content ON agent_memories BEGIN
    INSERT INTO agent_memories_fts(agent_memories_fts, rowid, content)
    VALUES('delete', old.id, old.content);
    INSERT INTO agent_memories_fts(rowid, content)
    VALUES (new.id, new.content);
END;
"""

SESSION_SELECT_SQL = """
SELECT
    id,
    user_id,
    title,
    source,
    model,
    model_config,
    system_prompt,
    parent_conversation_id AS parent_session_id,
    started_at,
    updated_at,
    ended_at,
    end_reason,
    message_count,
    tool_call_count,
    input_tokens,
    output_tokens,
    cache_read_tokens,
    cache_write_tokens,
    reasoning_tokens,
    billing_provider,
    billing_base_url,
    billing_mode,
    estimated_cost_usd,
    actual_cost_usd,
    cost_status,
    cost_source,
    pricing_version
FROM conversations
"""

MESSAGE_SELECT_SQL = """
SELECT
    id,
    conversation_id AS session_id,
    role,
    content,
    tool_call_id,
    tool_calls,
    tool_name,
    created_at AS timestamp,
    sequence,
    token_count,
    finish_reason,
    reasoning,
    reasoning_details,
    codex_reasoning_items
FROM conversation_messages
"""


class SessionDB:
    """
    SQLite-backed session storage with FTS5 search.

    Thread-safe for the common gateway pattern (multiple reader threads,
    single writer via WAL mode). Each method opens its own cursor.
    """

    # ── Write-contention tuning ──
    # With multiple hermes processes (gateway + CLI sessions + worktree agents)
    # all sharing one state.db, WAL write-lock contention causes visible TUI
    # freezes.  SQLite's built-in busy handler uses a deterministic sleep
    # schedule that causes convoy effects under high concurrency.
    #
    # Instead, we keep the SQLite timeout short (1s) and handle retries at the
    # application level with random jitter, which naturally staggers competing
    # writers and avoids the convoy.
    _WRITE_MAX_RETRIES = 15
    _WRITE_RETRY_MIN_S = 0.020   # 20ms
    _WRITE_RETRY_MAX_S = 0.150   # 150ms
    # Attempt a PASSIVE WAL checkpoint every N successful writes.
    _CHECKPOINT_EVERY_N_WRITES = 50

    def __init__(self, db_path: Path = None, *, readonly: bool = False):
        self.db_path = db_path or get_default_db_path()
        self._readonly = readonly
        if not self._readonly:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._write_count = 0
        connect_target = str(self.db_path)
        connect_kwargs: Dict[str, Any] = {}
        if self._readonly:
            connect_target = f"file:{self.db_path}?mode=ro"
            connect_kwargs["uri"] = True
        self._conn = sqlite3.connect(
            connect_target,
            check_same_thread=False,
            # Short timeout — application-level retry with random jitter
            # handles contention instead of sitting in SQLite's internal
            # busy handler for up to 30s.
            timeout=1.0,
            # Autocommit mode: Python's default isolation_level="" auto-starts
            # transactions on DML, which conflicts with our explicit
            # BEGIN IMMEDIATE.  None = we manage transactions ourselves.
            isolation_level=None,
            **connect_kwargs,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        if not self._readonly:
            self._conn.execute("PRAGMA journal_mode=WAL")

        if not self._readonly:
            self._init_schema()

    # ── Core write helper ──

    def _execute_write(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Execute a write transaction with BEGIN IMMEDIATE and jitter retry.

        *fn* receives the connection and should perform INSERT/UPDATE/DELETE
        statements.  The caller must NOT call ``commit()`` — that's handled
        here after *fn* returns.

        BEGIN IMMEDIATE acquires the WAL write lock at transaction start
        (not at commit time), so lock contention surfaces immediately.
        On ``database is locked``, we release the Python lock, sleep a
        random 20-150ms, and retry — breaking the convoy pattern that
        SQLite's built-in deterministic backoff creates.

        Returns whatever *fn* returns.
        """
        if self._readonly:
            raise RuntimeError("SessionDB opened in read-only mode")
        last_err: Optional[Exception] = None
        for attempt in range(self._WRITE_MAX_RETRIES):
            try:
                with self._lock:
                    self._conn.execute("BEGIN IMMEDIATE")
                    try:
                        result = fn(self._conn)
                        self._conn.commit()
                    except BaseException:
                        try:
                            self._conn.rollback()
                        except Exception:
                            pass
                        raise
                # Success — periodic best-effort checkpoint.
                self._write_count += 1
                if self._write_count % self._CHECKPOINT_EVERY_N_WRITES == 0:
                    self._try_wal_checkpoint()
                return result
            except sqlite3.OperationalError as exc:
                err_msg = str(exc).lower()
                if "locked" in err_msg or "busy" in err_msg:
                    last_err = exc
                    if attempt < self._WRITE_MAX_RETRIES - 1:
                        jitter = random.uniform(
                            self._WRITE_RETRY_MIN_S,
                            self._WRITE_RETRY_MAX_S,
                        )
                        time.sleep(jitter)
                        continue
                # Non-lock error or retries exhausted — propagate.
                raise
        # Retries exhausted (shouldn't normally reach here).
        raise last_err or sqlite3.OperationalError(
            "database is locked after max retries"
        )

    def _try_wal_checkpoint(self) -> None:
        """Best-effort PASSIVE WAL checkpoint.  Never blocks, never raises.

        Flushes committed WAL frames back into the main DB file for any
        frames that no other connection currently needs.  Keeps the WAL
        from growing unbounded when many processes hold persistent
        connections.
        """
        try:
            if self._readonly:
                return
            with self._lock:
                result = self._conn.execute(
                    "PRAGMA wal_checkpoint(PASSIVE)"
                ).fetchone()
                if result and result[1] > 0:
                    logger.debug(
                        "WAL checkpoint: %d/%d pages checkpointed",
                        result[2], result[1],
                    )
        except Exception:
            pass  # Best effort — never fatal.

    def close(self):
        """Close the database connection.

        Attempts a PASSIVE WAL checkpoint first so that exiting processes
        help keep the WAL file from growing unbounded.
        """
        with self._lock:
            if self._conn:
                if not self._readonly:
                    try:
                        self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    except Exception:
                        pass
                self._conn.close()
                self._conn = None

    @staticmethod
    def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
        row = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (table_name,),
        ).fetchone()
        return row is not None

    def _init_schema(self):
        """Create tables and FTS if they don't exist, run migrations."""
        cursor = self._conn.cursor()
        needs_conversation_rebuild = False

        cursor.executescript(BASE_SCHEMA_SQL)
        cursor.executescript(MOTIS_SCHEMA_SQL)
        has_legacy_sessions = self._table_exists(cursor, "sessions")
        has_legacy_messages = self._table_exists(cursor, "messages")

        # Check schema version and run migrations
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        current_version = int(row["version"]) if row is not None else 0

        if has_legacy_sessions and current_version < 2:
            try:
                cursor.execute("ALTER TABLE messages ADD COLUMN finish_reason TEXT")
            except sqlite3.OperationalError:
                pass
            current_version = 2

        if has_legacy_sessions and current_version < 3:
            try:
                cursor.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
            except sqlite3.OperationalError:
                pass
            current_version = 3

        if has_legacy_sessions and current_version < 4:
            try:
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_title_unique "
                    "ON sessions(title) WHERE title IS NOT NULL"
                )
            except sqlite3.OperationalError:
                pass
            current_version = 4

        if has_legacy_sessions and current_version < 5:
            new_columns = [
                ("cache_read_tokens", "INTEGER DEFAULT 0"),
                ("cache_write_tokens", "INTEGER DEFAULT 0"),
                ("reasoning_tokens", "INTEGER DEFAULT 0"),
                ("billing_provider", "TEXT"),
                ("billing_base_url", "TEXT"),
                ("billing_mode", "TEXT"),
                ("estimated_cost_usd", "REAL"),
                ("actual_cost_usd", "REAL"),
                ("cost_status", "TEXT"),
                ("cost_source", "TEXT"),
                ("pricing_version", "TEXT"),
            ]
            for name, column_type in new_columns:
                try:
                    safe_name = name.replace('"', '""')
                    cursor.execute(f'ALTER TABLE sessions ADD COLUMN "{safe_name}" {column_type}')
                except sqlite3.OperationalError:
                    pass
            current_version = 5

        if has_legacy_messages and current_version < 6:
            for col_name, col_type in [
                ("reasoning", "TEXT"),
                ("reasoning_details", "TEXT"),
                ("codex_reasoning_items", "TEXT"),
            ]:
                try:
                    safe = col_name.replace('"', '""')
                    cursor.execute(
                        f'ALTER TABLE messages ADD COLUMN "{safe}" {col_type}'
                    )
                except sqlite3.OperationalError:
                    pass
            current_version = 6

        if current_version < 8:
            try:
                cursor.execute("ALTER TABLE conversation_messages ADD COLUMN token_count INTEGER")
            except sqlite3.OperationalError:
                pass

            if has_legacy_sessions and has_legacy_messages:
                self._backfill_motis_storage(cursor)
                needs_conversation_rebuild = True

            if row is None:
                cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            else:
                cursor.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
        elif row is None:
            cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))

        try:
            cursor.execute("SELECT * FROM conversation_messages_fts LIMIT 0")
        except sqlite3.OperationalError:
            cursor.executescript(CONVERSATION_FTS_SQL)

        try:
            cursor.execute("SELECT * FROM agent_memories_fts LIMIT 0")
        except sqlite3.OperationalError:
            cursor.executescript(MEMORY_FTS_SQL)

        if needs_conversation_rebuild:
            try:
                cursor.execute(
                    "INSERT INTO conversation_messages_fts(conversation_messages_fts) "
                    "VALUES('rebuild')"
                )
            except sqlite3.OperationalError:
                pass

        self._conn.commit()

    def _backfill_motis_storage(self, cursor: sqlite3.Cursor) -> None:
        """Mirror legacy sessions/messages into Motis-style tables."""
        conn = cursor.connection

        session_rows = cursor.execute(
            "SELECT id FROM sessions ORDER BY started_at, id"
        ).fetchall()
        for row in session_rows:
            self._upsert_conversation_from_legacy(conn, row["id"])

        message_rows = cursor.execute(
            "SELECT id, session_id FROM messages ORDER BY session_id, timestamp, id"
        ).fetchall()
        sequence_by_session: Dict[str, int] = {}
        for row in message_rows:
            session_id = row["session_id"]
            sequence_by_session[session_id] = sequence_by_session.get(session_id, 0) + 1
            self._upsert_conversation_message_from_legacy(
                conn,
                row["id"],
                sequence=sequence_by_session[session_id],
            )

    def _upsert_conversation_from_legacy(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        *,
        fallback_source: Optional[str] = None,
        fallback_user_id: Optional[str] = None,
    ) -> None:
        session_row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if session_row is None:
            return

        source = normalize_storage_source(
            session_row["source"] or fallback_source,
            fallback="cli",
        )
        user_id = resolve_motis_user_id(
            session_row["user_id"] or fallback_user_id,
            source,
        )
        last_message_ts = conn.execute(
            "SELECT MAX(timestamp) FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        updated_at_candidates = [
            session_row["started_at"],
            last_message_ts,
            session_row["ended_at"],
        ]
        updated_at = max(
            (value for value in updated_at_candidates if value is not None),
            default=time.time(),
        )

        conn.execute(
            """
            INSERT INTO conversations (
                id, user_id, title, source, model, model_config, system_prompt,
                parent_conversation_id, started_at, updated_at, ended_at,
                end_reason, message_count, tool_call_count, input_tokens,
                output_tokens, cache_read_tokens, cache_write_tokens,
                reasoning_tokens, billing_provider, billing_base_url,
                billing_mode, estimated_cost_usd, actual_cost_usd, cost_status,
                cost_source, pricing_version
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id) DO UPDATE SET
                user_id = excluded.user_id,
                title = excluded.title,
                source = excluded.source,
                model = excluded.model,
                model_config = excluded.model_config,
                system_prompt = excluded.system_prompt,
                parent_conversation_id = excluded.parent_conversation_id,
                started_at = excluded.started_at,
                updated_at = excluded.updated_at,
                ended_at = excluded.ended_at,
                end_reason = excluded.end_reason,
                message_count = excluded.message_count,
                tool_call_count = excluded.tool_call_count,
                input_tokens = excluded.input_tokens,
                output_tokens = excluded.output_tokens,
                cache_read_tokens = excluded.cache_read_tokens,
                cache_write_tokens = excluded.cache_write_tokens,
                reasoning_tokens = excluded.reasoning_tokens,
                billing_provider = excluded.billing_provider,
                billing_base_url = excluded.billing_base_url,
                billing_mode = excluded.billing_mode,
                estimated_cost_usd = excluded.estimated_cost_usd,
                actual_cost_usd = excluded.actual_cost_usd,
                cost_status = excluded.cost_status,
                cost_source = excluded.cost_source,
                pricing_version = excluded.pricing_version
            """,
            (
                session_row["id"],
                user_id,
                session_row["title"],
                source,
                session_row["model"],
                session_row["model_config"],
                session_row["system_prompt"],
                session_row["parent_session_id"],
                session_row["started_at"],
                updated_at,
                session_row["ended_at"],
                session_row["end_reason"],
                session_row["message_count"],
                session_row["tool_call_count"],
                session_row["input_tokens"],
                session_row["output_tokens"],
                session_row["cache_read_tokens"],
                session_row["cache_write_tokens"],
                session_row["reasoning_tokens"],
                session_row["billing_provider"],
                session_row["billing_base_url"],
                session_row["billing_mode"],
                session_row["estimated_cost_usd"],
                session_row["actual_cost_usd"],
                session_row["cost_status"],
                session_row["cost_source"],
                session_row["pricing_version"],
            ),
        )

    def _upsert_conversation_message_from_legacy(
        self,
        conn: sqlite3.Connection,
        message_id: int,
        *,
        sequence: Optional[int] = None,
    ) -> None:
        row = conn.execute(
            """
            SELECT id, session_id, role, content, tool_call_id, tool_calls,
                   tool_name, timestamp, finish_reason, reasoning,
                   reasoning_details, codex_reasoning_items
            FROM messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
        if row is None:
            return

        self._upsert_conversation_from_legacy(conn, row["session_id"])

        if sequence is None:
            sequence = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM messages
                    WHERE session_id = ?
                      AND (timestamp < ? OR (timestamp = ? AND id <= ?))
                    """,
                    (
                        row["session_id"],
                        row["timestamp"],
                        row["timestamp"],
                        row["id"],
                    ),
                ).fetchone()[0]
            )

        conn.execute(
            """
            INSERT INTO conversation_messages (
                id, conversation_id, role, content, tool_call_id, tool_calls,
                tool_name, created_at, sequence, finish_reason, reasoning,
                reasoning_details, codex_reasoning_items
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                conversation_id = excluded.conversation_id,
                role = excluded.role,
                content = excluded.content,
                tool_call_id = excluded.tool_call_id,
                tool_calls = excluded.tool_calls,
                tool_name = excluded.tool_name,
                created_at = excluded.created_at,
                sequence = excluded.sequence,
                finish_reason = excluded.finish_reason,
                reasoning = excluded.reasoning,
                reasoning_details = excluded.reasoning_details,
                codex_reasoning_items = excluded.codex_reasoning_items
            """,
            (
                row["id"],
                row["session_id"],
                row["role"],
                row["content"],
                row["tool_call_id"],
                row["tool_calls"],
                row["tool_name"],
                row["timestamp"],
                sequence,
                row["finish_reason"],
                row["reasoning"],
                row["reasoning_details"],
                row["codex_reasoning_items"],
            ),
        )

    @staticmethod
    def _normalize_memory_target(target: str) -> str:
        normalized = str(target or "").strip().lower()
        if normalized not in {"memory", "user"}:
            raise ValueError(f"Unsupported memory target '{target}'")
        return normalized

    def get_memory_entries(self, user_id: str, target: str) -> List[Dict[str, Any]]:
        """Return structured built-in memory entries for a Motis user."""
        normalized_target = self._normalize_memory_target(target)
        resolved_user_id = resolve_motis_user_id(user_id)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, user_id, target, content, type, tags, source,
                       importance, position, created_at, updated_at
                FROM agent_memories
                WHERE user_id = ? AND target = ?
                ORDER BY position, id
                """,
                (resolved_user_id, normalized_target),
            ).fetchall()
        return [dict(row) for row in rows]

    def replace_memory_entries(
        self,
        user_id: str,
        target: str,
        entries: List[str],
        *,
        source: str = "builtin",
    ) -> None:
        """Replace the ordered memory entries for one target atomically."""
        normalized_target = self._normalize_memory_target(target)
        resolved_user_id = resolve_motis_user_id(user_id)
        normalized_source = normalize_storage_source(source, fallback="builtin")
        deduped_entries = list(
            dict.fromkeys(
                entry.strip()
                for entry in entries
                if isinstance(entry, str) and entry.strip()
            )
        )

        def _do(conn):
            existing_rows = conn.execute(
                """
                SELECT content, created_at
                FROM agent_memories
                WHERE user_id = ? AND target = ?
                """,
                (resolved_user_id, normalized_target),
            ).fetchall()
            created_at_by_content = {
                row["content"]: row["created_at"]
                for row in existing_rows
            }

            conn.execute(
                "DELETE FROM agent_memories WHERE user_id = ? AND target = ?",
                (resolved_user_id, normalized_target),
            )

            now = time.time()
            memory_type = "user_profile" if normalized_target == "user" else "agent_note"
            for position, content in enumerate(deduped_entries, start=1):
                conn.execute(
                    """
                    INSERT INTO agent_memories (
                        user_id, target, content, type, tags, source,
                        importance, position, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resolved_user_id,
                        normalized_target,
                        content,
                        memory_type,
                        "[]",
                        normalized_source,
                        5,
                        position,
                        created_at_by_content.get(content, now),
                        now,
                    ),
                )

        self._execute_write(_do)

    # =========================================================================
    # Session lifecycle
    # =========================================================================

    def create_session(
        self,
        session_id: str,
        source: str,
        model: str = None,
        model_config: Dict[str, Any] = None,
        system_prompt: str = None,
        user_id: str = None,
        parent_session_id: str = None,
    ) -> str:
        """Create a new session record. Returns the session_id."""
        normalized_source = normalize_storage_source(source, fallback="cli")
        resolved_user_id = resolve_motis_user_id(user_id, normalized_source)
        started_at = time.time()

        def _do(conn):
            conn.execute(
                """
                INSERT OR IGNORE INTO conversations (
                    id, user_id, title, source, model, model_config, system_prompt,
                    parent_conversation_id, started_at, updated_at, ended_at,
                    end_reason, message_count, tool_call_count, input_tokens,
                    output_tokens, cache_read_tokens, cache_write_tokens,
                    reasoning_tokens, billing_provider, billing_base_url,
                    billing_mode, estimated_cost_usd, actual_cost_usd, cost_status,
                    cost_source, pricing_version
                ) VALUES (
                    ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, 0, 0, 0, 0,
                    0, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
                )
                """,
                (
                    session_id,
                    resolved_user_id,
                    normalized_source,
                    model,
                    json.dumps(model_config) if model_config else None,
                    system_prompt,
                    parent_session_id,
                    started_at,
                    started_at,
                ),
            )
        self._execute_write(_do)
        return session_id

    def end_session(self, session_id: str, end_reason: str) -> None:
        """Mark a session as ended."""
        def _do(conn):
            conn.execute(
                "UPDATE conversations SET ended_at = ?, end_reason = ?, updated_at = ? WHERE id = ?",
                (time.time(), end_reason, time.time(), session_id),
            )
        self._execute_write(_do)

    def reopen_session(self, session_id: str) -> None:
        """Clear ended_at/end_reason so a session can be resumed."""
        def _do(conn):
            conn.execute(
                "UPDATE conversations SET ended_at = NULL, end_reason = NULL, updated_at = ? WHERE id = ?",
                (time.time(), session_id),
            )
        self._execute_write(_do)

    def update_system_prompt(self, session_id: str, system_prompt: str) -> None:
        """Store the full assembled system prompt snapshot."""
        def _do(conn):
            conn.execute(
                "UPDATE conversations SET system_prompt = ?, updated_at = ? WHERE id = ?",
                (system_prompt, time.time(), session_id),
            )
        self._execute_write(_do)

    def update_token_counts(
        self,
        session_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = None,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
        estimated_cost_usd: Optional[float] = None,
        actual_cost_usd: Optional[float] = None,
        cost_status: Optional[str] = None,
        cost_source: Optional[str] = None,
        pricing_version: Optional[str] = None,
        billing_provider: Optional[str] = None,
        billing_base_url: Optional[str] = None,
        billing_mode: Optional[str] = None,
        absolute: bool = False,
    ) -> None:
        """Update token counters and backfill model if not already set.

        When *absolute* is False (default), values are **incremented** — use
        this for per-API-call deltas (CLI path).

        When *absolute* is True, values are **set directly** — use this when
        the caller already holds cumulative totals (gateway path, where the
        cached agent accumulates across messages).
        """
        if absolute:
            sql = """UPDATE conversations SET
                   input_tokens = ?,
                   output_tokens = ?,
                   cache_read_tokens = ?,
                   cache_write_tokens = ?,
                   reasoning_tokens = ?,
                   estimated_cost_usd = COALESCE(?, 0),
                   actual_cost_usd = CASE
                       WHEN ? IS NULL THEN actual_cost_usd
                       ELSE ?
                   END,
                   cost_status = COALESCE(?, cost_status),
                   cost_source = COALESCE(?, cost_source),
                   pricing_version = COALESCE(?, pricing_version),
                   billing_provider = COALESCE(billing_provider, ?),
                   billing_base_url = COALESCE(billing_base_url, ?),
                   billing_mode = COALESCE(billing_mode, ?),
                   updated_at = ?,
                   model = COALESCE(model, ?)
                   WHERE id = ?"""
        else:
            sql = """UPDATE conversations SET
                   input_tokens = input_tokens + ?,
                   output_tokens = output_tokens + ?,
                   cache_read_tokens = cache_read_tokens + ?,
                   cache_write_tokens = cache_write_tokens + ?,
                   reasoning_tokens = reasoning_tokens + ?,
                   estimated_cost_usd = COALESCE(estimated_cost_usd, 0) + COALESCE(?, 0),
                   actual_cost_usd = CASE
                       WHEN ? IS NULL THEN actual_cost_usd
                       ELSE COALESCE(actual_cost_usd, 0) + ?
                   END,
                   cost_status = COALESCE(?, cost_status),
                   cost_source = COALESCE(?, cost_source),
                   pricing_version = COALESCE(?, pricing_version),
                   billing_provider = COALESCE(billing_provider, ?),
                   billing_base_url = COALESCE(billing_base_url, ?),
                   billing_mode = COALESCE(billing_mode, ?),
                   updated_at = ?,
                   model = COALESCE(model, ?)
                   WHERE id = ?"""
        params = (
            input_tokens,
            output_tokens,
            cache_read_tokens,
            cache_write_tokens,
            reasoning_tokens,
            estimated_cost_usd,
            actual_cost_usd,
            actual_cost_usd,
            cost_status,
            cost_source,
            pricing_version,
            billing_provider,
            billing_base_url,
            billing_mode,
            time.time(),
            model,
            session_id,
        )
        def _do(conn):
            conn.execute(sql, params)
        self._execute_write(_do)

    def ensure_session(
        self,
        session_id: str,
        source: str = "unknown",
        model: str = None,
        user_id: str = None,
    ) -> None:
        """Ensure a session row exists, creating it with minimal metadata if absent.

        Used by _flush_messages_to_session_db to recover from a failed
        create_session() call (e.g. transient SQLite lock at agent startup).
        INSERT OR IGNORE is safe to call even when the row already exists.
        """
        normalized_source = normalize_storage_source(source, fallback="cli")
        resolved_user_id = resolve_motis_user_id(user_id, normalized_source)

        def _do(conn):
            conn.execute(
                """
                INSERT OR IGNORE INTO conversations (
                    id, user_id, title, source, model, model_config, system_prompt,
                    parent_conversation_id, started_at, updated_at, ended_at,
                    end_reason, message_count, tool_call_count, input_tokens,
                    output_tokens, cache_read_tokens, cache_write_tokens,
                    reasoning_tokens, billing_provider, billing_base_url,
                    billing_mode, estimated_cost_usd, actual_cost_usd, cost_status,
                    cost_source, pricing_version
                ) VALUES (
                    ?, ?, NULL, ?, ?, NULL, NULL, NULL, ?, ?, NULL, NULL, 0, 0,
                    0, 0, 0, 0, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
                )
                """,
                (session_id, resolved_user_id, normalized_source, model, time.time(), time.time()),
            )
        self._execute_write(_do)

    def set_token_counts(
        self,
        session_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = None,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
        estimated_cost_usd: Optional[float] = None,
        actual_cost_usd: Optional[float] = None,
        cost_status: Optional[str] = None,
        cost_source: Optional[str] = None,
        pricing_version: Optional[str] = None,
        billing_provider: Optional[str] = None,
        billing_base_url: Optional[str] = None,
        billing_mode: Optional[str] = None,
    ) -> None:
        """Set token counters to absolute values (not increment).

        Use this when the caller provides cumulative totals from a completed
        conversation run (e.g. the gateway, where the cached agent's
        session_prompt_tokens already reflects the running total).
        """
        def _do(conn):
            conn.execute(
                """UPDATE conversations SET
                   input_tokens = ?,
                   output_tokens = ?,
                   cache_read_tokens = ?,
                   cache_write_tokens = ?,
                   reasoning_tokens = ?,
                   estimated_cost_usd = ?,
                   actual_cost_usd = CASE
                       WHEN ? IS NULL THEN actual_cost_usd
                       ELSE ?
                   END,
                   cost_status = COALESCE(?, cost_status),
                   cost_source = COALESCE(?, cost_source),
                   pricing_version = COALESCE(?, pricing_version),
                   billing_provider = COALESCE(billing_provider, ?),
                   billing_base_url = COALESCE(billing_base_url, ?),
                   billing_mode = COALESCE(billing_mode, ?),
                   updated_at = ?,
                   model = COALESCE(model, ?)
                   WHERE id = ?""",
                (
                    input_tokens,
                    output_tokens,
                    cache_read_tokens,
                    cache_write_tokens,
                    reasoning_tokens,
                    estimated_cost_usd,
                    actual_cost_usd,
                    actual_cost_usd,
                    cost_status,
                    cost_source,
                    pricing_version,
                    billing_provider,
                    billing_base_url,
                    billing_mode,
                    time.time(),
                    model,
                    session_id,
                ),
            )
        self._execute_write(_do)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        with self._lock:
            cursor = self._conn.execute(
                f"{SESSION_SELECT_SQL} WHERE id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    def resolve_session_id(self, session_id_or_prefix: str) -> Optional[str]:
        """Resolve an exact or uniquely prefixed session ID to the full ID.

        Returns the exact ID when it exists. Otherwise treats the input as a
        prefix and returns the single matching session ID if the prefix is
        unambiguous. Returns None for no matches or ambiguous prefixes.
        """
        exact = self.get_session(session_id_or_prefix)
        if exact:
            return exact["id"]

        escaped = (
            session_id_or_prefix
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id FROM conversations WHERE id LIKE ? ESCAPE '\\' ORDER BY started_at DESC LIMIT 2",
                (f"{escaped}%",),
            )
            matches = [row["id"] for row in cursor.fetchall()]
        if len(matches) == 1:
            return matches[0]
        return None

    # Maximum length for session titles
    MAX_TITLE_LENGTH = 100

    @staticmethod
    def sanitize_title(title: Optional[str]) -> Optional[str]:
        """Validate and sanitize a session title.

        - Strips leading/trailing whitespace
        - Removes ASCII control characters (0x00-0x1F, 0x7F) and problematic
          Unicode control chars (zero-width, RTL/LTR overrides, etc.)
        - Collapses internal whitespace runs to single spaces
        - Normalizes empty/whitespace-only strings to None
        - Enforces MAX_TITLE_LENGTH

        Returns the cleaned title string or None.
        Raises ValueError if the title exceeds MAX_TITLE_LENGTH after cleaning.
        """
        if not title:
            return None

        # Remove ASCII control characters (0x00-0x1F, 0x7F) but keep
        # whitespace chars (\t=0x09, \n=0x0A, \r=0x0D) so they can be
        # normalized to spaces by the whitespace collapsing step below
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', title)

        # Remove problematic Unicode control characters:
        # - Zero-width chars (U+200B-U+200F, U+FEFF)
        # - Directional overrides (U+202A-U+202E, U+2066-U+2069)
        # - Object replacement (U+FFFC), interlinear annotation (U+FFF9-U+FFFB)
        cleaned = re.sub(
            r'[\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff\ufffc\ufff9-\ufffb]',
            '', cleaned,
        )

        # Collapse internal whitespace runs and strip
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        if not cleaned:
            return None

        if len(cleaned) > SessionDB.MAX_TITLE_LENGTH:
            raise ValueError(
                f"Title too long ({len(cleaned)} chars, max {SessionDB.MAX_TITLE_LENGTH})"
            )

        return cleaned

    def set_session_title(self, session_id: str, title: str) -> bool:
        """Set or update a session's title.

        Returns True if session was found and title was set.
        Raises ValueError if title is already in use by another session,
        or if the title fails validation (too long, invalid characters).
        Empty/whitespace-only strings are normalized to None (clearing the title).
        """
        title = self.sanitize_title(title)
        def _do(conn):
            if title:
                # Check uniqueness (allow the same session to keep its own title)
                cursor = conn.execute(
                    "SELECT id FROM conversations WHERE title = ? AND id != ?",
                    (title, session_id),
                )
                conflict = cursor.fetchone()
                if conflict:
                    raise ValueError(
                        f"Title '{title}' is already in use by session {conflict['id']}"
                    )
            cursor = conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, time.time(), session_id),
            )
            return cursor.rowcount
        rowcount = self._execute_write(_do)
        return rowcount > 0

    def get_session_title(self, session_id: str) -> Optional[str]:
        """Get the title for a session, or None."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT title FROM conversations WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
        return row["title"] if row else None

    def get_session_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Look up a session by exact title. Returns session dict or None."""
        with self._lock:
            cursor = self._conn.execute(
                f"{SESSION_SELECT_SQL} WHERE title = ?",
                (title,),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    def resolve_session_by_title(self, title: str) -> Optional[str]:
        """Resolve a title to a session ID, preferring the latest in a lineage.

        If the exact title exists, returns that session's ID.
        If not, searches for "title #N" variants and returns the latest one.
        If the exact title exists AND numbered variants exist, returns the
        latest numbered variant (the most recent continuation).
        """
        # First try exact match
        exact = self.get_session_by_title(title)

        # Also search for numbered variants: "title #2", "title #3", etc.
        # Escape SQL LIKE wildcards (%, _) in the title to prevent false matches
        escaped = title.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id, title, started_at FROM conversations "
                "WHERE title LIKE ? ESCAPE '\\' ORDER BY started_at DESC",
                (f"{escaped} #%",),
            )
            numbered = cursor.fetchall()

        if numbered:
            # Return the most recent numbered variant
            return numbered[0]["id"]
        elif exact:
            return exact["id"]
        return None

    def get_next_title_in_lineage(self, base_title: str) -> str:
        """Generate the next title in a lineage (e.g., "my session" → "my session #2").

        Strips any existing " #N" suffix to find the base name, then finds
        the highest existing number and increments.
        """
        # Strip existing #N suffix to find the true base
        match = re.match(r'^(.*?) #(\d+)$', base_title)
        if match:
            base = match.group(1)
        else:
            base = base_title

        # Find all existing numbered variants
        # Escape SQL LIKE wildcards (%, _) in the base to prevent false matches
        escaped = base.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._lock:
            cursor = self._conn.execute(
                "SELECT title FROM conversations WHERE title = ? OR title LIKE ? ESCAPE '\\'",
                (base, f"{escaped} #%"),
            )
            existing = [row["title"] for row in cursor.fetchall()]

        if not existing:
            return base  # No conflict, use the base name as-is

        # Find the highest number
        max_num = 1  # The unnumbered original counts as #1
        for t in existing:
            m = re.match(r'^.* #(\d+)$', t)
            if m:
                max_num = max(max_num, int(m.group(1)))

        return f"{base} #{max_num + 1}"

    def list_sessions_rich(
        self,
        source: str = None,
        exclude_sources: List[str] = None,
        limit: int = 20,
        offset: int = 0,
        include_children: bool = False,
    ) -> List[Dict[str, Any]]:
        """List sessions with preview (first user message) and last active timestamp.

        Returns dicts with keys: id, source, model, title, started_at, ended_at,
        message_count, preview (first 60 chars of first user message),
        last_active (timestamp of last message).

        Uses a single query with correlated subqueries instead of N+2 queries.

        By default, child sessions (subagent runs, compression continuations)
        are excluded.  Pass ``include_children=True`` to include them.
        """
        where_clauses = []
        params = []

        if not include_children:
            where_clauses.append("s.parent_session_id IS NULL")

        if source:
            where_clauses.append("s.source = ?")
            params.append(source)
        if exclude_sources:
            placeholders = ",".join("?" for _ in exclude_sources)
            where_clauses.append(f"s.source NOT IN ({placeholders})")
            params.extend(exclude_sources)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"""
            SELECT s.*,
                COALESCE(
                    (SELECT SUBSTR(REPLACE(REPLACE(m.content, X'0A', ' '), X'0D', ' '), 1, 63)
                     FROM conversation_messages m
                     WHERE m.conversation_id = s.id AND m.role = 'user' AND m.content IS NOT NULL
                     ORDER BY m.sequence, m.id LIMIT 1),
                    ''
                ) AS _preview_raw,
                COALESCE(
                    (SELECT MAX(m2.created_at) FROM conversation_messages m2 WHERE m2.conversation_id = s.id),
                    s.updated_at,
                    s.started_at
                ) AS last_active
            FROM (
                SELECT
                    id,
                    user_id,
                    title,
                    source,
                    model,
                    model_config,
                    system_prompt,
                    parent_conversation_id AS parent_session_id,
                    started_at,
                    updated_at,
                    ended_at,
                    end_reason,
                    message_count,
                    tool_call_count,
                    input_tokens,
                    output_tokens,
                    cache_read_tokens,
                    cache_write_tokens,
                    reasoning_tokens,
                    billing_provider,
                    billing_base_url,
                    billing_mode,
                    estimated_cost_usd,
                    actual_cost_usd,
                    cost_status,
                    cost_source,
                    pricing_version
                FROM conversations
            ) s
            {where_sql}
            ORDER BY s.started_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        with self._lock:
            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
        sessions = []
        for row in rows:
            s = dict(row)
            # Build the preview from the raw substring
            raw = s.pop("_preview_raw", "").strip()
            if raw:
                text = raw[:60]
                s["preview"] = text + ("..." if len(raw) > 60 else "")
            else:
                s["preview"] = ""
            sessions.append(s)

        return sessions

    # =========================================================================
    # Message storage
    # =========================================================================

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str = None,
        tool_name: str = None,
        tool_calls: Any = None,
        tool_call_id: str = None,
        token_count: int = None,
        finish_reason: str = None,
        reasoning: str = None,
        reasoning_details: Any = None,
        codex_reasoning_items: Any = None,
    ) -> int:
        """
        Append a message to a session. Returns the message row ID.

        Also increments the session's message_count (and tool_call_count
        if role is 'tool' or tool_calls is present).
        """
        # Serialize structured fields to JSON before entering the write txn
        reasoning_details_json = (
            json.dumps(reasoning_details)
            if reasoning_details else None
        )
        codex_items_json = (
            json.dumps(codex_reasoning_items)
            if codex_reasoning_items else None
        )
        tool_calls_json = json.dumps(tool_calls) if tool_calls else None

        # Pre-compute tool call count
        num_tool_calls = 0
        if tool_calls is not None:
            num_tool_calls = len(tool_calls) if isinstance(tool_calls, list) else 1

        def _do(conn):
            now = time.time()
            session_row = conn.execute(
                "SELECT message_count FROM conversations WHERE id = ?",
                (session_id,),
            ).fetchone()
            next_sequence = (int(session_row["message_count"]) if session_row else 0) + 1
            cursor = conn.execute(
                """INSERT INTO conversation_messages (conversation_id, role, content, tool_call_id,
                   tool_calls, tool_name, created_at, sequence, token_count, finish_reason,
                   reasoning, reasoning_details, codex_reasoning_items)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    role,
                    content,
                    tool_call_id,
                    tool_calls_json,
                    tool_name,
                    now,
                    next_sequence,
                    token_count,
                    finish_reason,
                    reasoning,
                    reasoning_details_json,
                    codex_items_json,
                ),
            )
            msg_id = cursor.lastrowid

            # Update counters
            if num_tool_calls > 0:
                conn.execute(
                    """UPDATE conversations SET message_count = ?, updated_at = ?,
                       tool_call_count = tool_call_count + ? WHERE id = ?""",
                    (next_sequence, now, num_tool_calls, session_id),
                )
            else:
                conn.execute(
                    "UPDATE conversations SET message_count = ?, updated_at = ? WHERE id = ?",
                    (next_sequence, now, session_id),
                )
            return msg_id

        return self._execute_write(_do)

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Load all messages for a session, ordered by timestamp."""
        with self._lock:
            cursor = self._conn.execute(
                f"{MESSAGE_SELECT_SQL} WHERE conversation_id = ? ORDER BY sequence, id",
                (session_id,),
            )
            rows = cursor.fetchall()
        result = []
        for row in rows:
            msg = dict(row)
            if msg.get("tool_calls"):
                try:
                    msg["tool_calls"] = json.loads(msg["tool_calls"])
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to deserialize tool_calls in get_messages, falling back to []")
                    msg["tool_calls"] = []
            result.append(msg)
        return result

    def get_messages_as_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Load messages in the OpenAI conversation format (role + content dicts).
        Used by the gateway to restore conversation history.
        """
        with self._lock:
            cursor = self._conn.execute(
                "SELECT role, content, tool_call_id, tool_calls, tool_name, "
                "reasoning, reasoning_details, codex_reasoning_items "
                "FROM conversation_messages WHERE conversation_id = ? ORDER BY sequence, id",
                (session_id,),
            )
            rows = cursor.fetchall()
        messages = []
        for row in rows:
            msg = {"role": row["role"], "content": row["content"]}
            if row["tool_call_id"]:
                msg["tool_call_id"] = row["tool_call_id"]
            if row["tool_name"]:
                msg["tool_name"] = row["tool_name"]
            if row["tool_calls"]:
                try:
                    msg["tool_calls"] = json.loads(row["tool_calls"])
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to deserialize tool_calls in conversation replay, falling back to []")
                    msg["tool_calls"] = []
            # Restore reasoning fields on assistant messages so providers
            # that replay reasoning (OpenRouter, OpenAI, Nous) receive
            # coherent multi-turn reasoning context.
            if row["role"] == "assistant":
                if row["reasoning"]:
                    msg["reasoning"] = row["reasoning"]
                if row["reasoning_details"]:
                    try:
                        msg["reasoning_details"] = json.loads(row["reasoning_details"])
                    except (json.JSONDecodeError, TypeError):
                        logger.warning("Failed to deserialize reasoning_details, falling back to None")
                        msg["reasoning_details"] = None
                if row["codex_reasoning_items"]:
                    try:
                        msg["codex_reasoning_items"] = json.loads(row["codex_reasoning_items"])
                    except (json.JSONDecodeError, TypeError):
                        logger.warning("Failed to deserialize codex_reasoning_items, falling back to None")
                        msg["codex_reasoning_items"] = None
            messages.append(msg)
        return messages

    # =========================================================================
    # Search
    # =========================================================================

    @staticmethod
    def _sanitize_fts5_query(query: str) -> str:
        """Sanitize user input for safe use in FTS5 MATCH queries.

        FTS5 has its own query syntax where characters like ``"``, ``(``, ``)``,
        ``+``, ``*``, ``{``, ``}`` and bare boolean operators (``AND``, ``OR``,
        ``NOT``) have special meaning.  Passing raw user input directly to
        MATCH can cause ``sqlite3.OperationalError``.

        Strategy:
        - Preserve properly paired quoted phrases (``"exact phrase"``)
        - Strip unmatched FTS5-special characters that would cause errors
        - Wrap unquoted hyphenated and dotted terms in quotes so FTS5
          matches them as exact phrases instead of splitting on the
          hyphen/dot (e.g. ``chat-send``, ``P2.2``, ``my-app.config.ts``)
        """
        # Step 1: Extract balanced double-quoted phrases and protect them
        # from further processing via numbered placeholders.
        _quoted_parts: list = []

        def _preserve_quoted(m: re.Match) -> str:
            _quoted_parts.append(m.group(0))
            return f"\x00Q{len(_quoted_parts) - 1}\x00"

        sanitized = re.sub(r'"[^"]*"', _preserve_quoted, query)

        # Step 2: Strip remaining (unmatched) FTS5-special characters
        sanitized = re.sub(r'[+{}()\"^]', " ", sanitized)

        # Step 3: Collapse repeated * (e.g. "***") into a single one,
        # and remove leading * (prefix-only needs at least one char before *)
        sanitized = re.sub(r"\*+", "*", sanitized)
        sanitized = re.sub(r"(^|\s)\*", r"\1", sanitized)

        # Step 4: Remove dangling boolean operators at start/end that would
        # cause syntax errors (e.g. "hello AND" or "OR world")
        sanitized = re.sub(r"(?i)^(AND|OR|NOT)\b\s*", "", sanitized.strip())
        sanitized = re.sub(r"(?i)\s+(AND|OR|NOT)\s*$", "", sanitized.strip())

        # Step 5: Wrap unquoted dotted and/or hyphenated terms in double
        # quotes.  FTS5's tokenizer splits on dots and hyphens, turning
        # ``chat-send`` into ``chat AND send`` and ``P2.2`` into ``p2 AND 2``.
        # Quoting preserves phrase semantics.  A single pass avoids the
        # double-quoting bug that would occur if dotted and hyphenated
        # patterns were applied sequentially (e.g. ``my-app.config``).
        sanitized = re.sub(r"\b(\w+(?:[.-]\w+)+)\b", r'"\1"', sanitized)

        # Step 6: Restore preserved quoted phrases
        for i, quoted in enumerate(_quoted_parts):
            sanitized = sanitized.replace(f"\x00Q{i}\x00", quoted)

        return sanitized.strip()

    def search_messages(
        self,
        query: str,
        source_filter: List[str] = None,
        exclude_sources: List[str] = None,
        role_filter: List[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Full-text search across session messages using FTS5.

        Supports FTS5 query syntax:
          - Simple keywords: "docker deployment"
          - Phrases: '"exact phrase"'
          - Boolean: "docker OR kubernetes", "python NOT java"
          - Prefix: "deploy*"

        Returns matching messages with session metadata, content snippet,
        and surrounding context (1 message before and after the match).
        """
        if not query or not query.strip():
            return []

        query = self._sanitize_fts5_query(query)
        if not query:
            return []

        # Build WHERE clauses dynamically
        where_clauses = ["conversation_messages_fts MATCH ?"]
        params: list = [query]

        if source_filter is not None:
            source_placeholders = ",".join("?" for _ in source_filter)
            where_clauses.append(f"s.source IN ({source_placeholders})")
            params.extend(source_filter)

        if exclude_sources is not None:
            exclude_placeholders = ",".join("?" for _ in exclude_sources)
            where_clauses.append(f"s.source NOT IN ({exclude_placeholders})")
            params.extend(exclude_sources)

        if role_filter:
            role_placeholders = ",".join("?" for _ in role_filter)
            where_clauses.append(f"m.role IN ({role_placeholders})")
            params.extend(role_filter)

        where_sql = " AND ".join(where_clauses)
        params.extend([limit, offset])

        sql = f"""
            SELECT
                m.id,
                m.conversation_id AS session_id,
                m.role,
                snippet(conversation_messages_fts, 0, '>>>', '<<<', '...', 40) AS snippet,
                m.content,
                m.created_at AS timestamp,
                m.sequence,
                m.tool_name,
                s.source,
                s.model,
                s.started_at AS session_started
            FROM conversation_messages_fts
            JOIN conversation_messages m ON m.id = conversation_messages_fts.rowid
            JOIN conversations s ON s.id = m.conversation_id
            WHERE {where_sql}
            ORDER BY rank
            LIMIT ? OFFSET ?
        """

        with self._lock:
            try:
                cursor = self._conn.execute(sql, params)
            except sqlite3.OperationalError:
                # FTS5 query syntax error despite sanitization — return empty
                return []
            matches = [dict(row) for row in cursor.fetchall()]

        # Add surrounding context (1 message before + after each match).
        # Done outside the lock so we don't hold it across N sequential queries.
        for match in matches:
            try:
                with self._lock:
                    ctx_cursor = self._conn.execute(
                        """SELECT role, content FROM conversation_messages
                           WHERE conversation_id = ?
                             AND sequence BETWEEN ? - 1 AND ? + 1
                           ORDER BY sequence, id""",
                        (match["session_id"], match["sequence"], match["sequence"]),
                    )
                    context_msgs = [
                        {"role": r["role"], "content": (r["content"] or "")[:200]}
                        for r in ctx_cursor.fetchall()
                    ]
                match["context"] = context_msgs
            except Exception:
                match["context"] = []

        # Remove full content from result (snippet is enough, saves tokens)
        for match in matches:
            match.pop("content", None)

        return matches

    def search_sessions(
        self,
        source: str = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List sessions, optionally filtered by source."""
        with self._lock:
            if source:
                cursor = self._conn.execute(
                    f"{SESSION_SELECT_SQL} WHERE source = ? ORDER BY started_at DESC LIMIT ? OFFSET ?",
                    (source, limit, offset),
                )
            else:
                cursor = self._conn.execute(
                    f"{SESSION_SELECT_SQL} ORDER BY started_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # Utility
    # =========================================================================

    def session_count(self, source: str = None) -> int:
        """Count sessions, optionally filtered by source."""
        with self._lock:
            if source:
                cursor = self._conn.execute(
                    "SELECT COUNT(*) FROM conversations WHERE source = ?", (source,)
                )
            else:
                cursor = self._conn.execute("SELECT COUNT(*) FROM conversations")
            return cursor.fetchone()[0]

    def message_count(self, session_id: str = None) -> int:
        """Count messages, optionally for a specific session."""
        with self._lock:
            if session_id:
                cursor = self._conn.execute(
                    "SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = ?", (session_id,)
                )
            else:
                cursor = self._conn.execute("SELECT COUNT(*) FROM conversation_messages")
            return cursor.fetchone()[0]

    # =========================================================================
    # Export and cleanup
    # =========================================================================

    def export_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Export a single session with all its messages as a dict."""
        session = self.get_session(session_id)
        if not session:
            return None
        messages = self.get_messages(session_id)
        return {**session, "messages": messages}

    def export_all(self, source: str = None) -> List[Dict[str, Any]]:
        """
        Export all sessions (with messages) as a list of dicts.
        Suitable for writing to a JSONL file for backup/analysis.
        """
        sessions = self.search_sessions(source=source, limit=100000)
        results = []
        for session in sessions:
            messages = self.get_messages(session["id"])
            results.append({**session, "messages": messages})
        return results

    def clear_messages(self, session_id: str) -> None:
        """Delete all messages for a session and reset its counters."""
        def _do(conn):
            conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?",
                (session_id,),
            )
            conn.execute(
                "UPDATE conversations SET message_count = 0, tool_call_count = 0, updated_at = ? WHERE id = ?",
                (time.time(), session_id),
            )
        self._execute_write(_do)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages.

        Child sessions are orphaned (parent_session_id set to NULL) rather
        than cascade-deleted, so they remain accessible independently.
        Returns True if the session was found and deleted.
        """
        def _do(conn):
            cursor = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE id = ?", (session_id,)
            )
            if cursor.fetchone()[0] == 0:
                return False
            # Orphan child sessions so FK constraint is satisfied
            conn.execute(
                "UPDATE conversations SET parent_conversation_id = NULL "
                "WHERE parent_conversation_id = ?",
                (session_id,),
            )
            conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?",
                (session_id,),
            )
            conn.execute("DELETE FROM conversations WHERE id = ?", (session_id,))
            return True
        return self._execute_write(_do)

    def prune_sessions(self, older_than_days: int = 90, source: str = None) -> int:
        """Delete sessions older than N days. Returns count of deleted sessions.

        Only prunes ended sessions (not active ones).  Child sessions outside
        the prune window are orphaned (parent_session_id set to NULL) rather
        than cascade-deleted.
        """
        cutoff = time.time() - (older_than_days * 86400)

        def _do(conn):
            if source:
                cursor = conn.execute(
                    """SELECT id FROM conversations
                       WHERE started_at < ? AND ended_at IS NOT NULL AND source = ?""",
                    (cutoff, source),
                )
            else:
                cursor = conn.execute(
                    "SELECT id FROM conversations WHERE started_at < ? AND ended_at IS NOT NULL",
                    (cutoff,),
                )
            session_ids = set(row["id"] for row in cursor.fetchall())

            if not session_ids:
                return 0

            # Orphan any sessions whose parent is about to be deleted
            placeholders = ",".join("?" * len(session_ids))
            conn.execute(
                f"UPDATE conversations SET parent_conversation_id = NULL "
                f"WHERE parent_conversation_id IN ({placeholders})",
                list(session_ids),
            )

            for sid in session_ids:
                conn.execute(
                    "DELETE FROM conversation_messages WHERE conversation_id = ?",
                    (sid,),
                )
                conn.execute("DELETE FROM conversations WHERE id = ?", (sid,))
            return len(session_ids)

        return self._execute_write(_do)
