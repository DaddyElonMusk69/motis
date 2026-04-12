from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

from motis_state import SessionDB


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
    return {row[0] for row in rows}


def test_fresh_db_bootstraps_motis_tables_only(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    db = SessionDB(db_path=db_path)
    db.close()

    tables = _table_names(db_path)

    assert "conversations" in tables
    assert "conversation_messages" in tables
    assert "agent_memories" in tables
    assert "conversation_messages_fts" in tables
    assert "agent_memories_fts" in tables
    assert "sessions" not in tables
    assert "messages" not in tables
    assert "messages_fts" not in tables


def test_sessiondb_uses_conversation_tables_for_runtime_crud(tmp_path: Path) -> None:
    db = SessionDB(db_path=tmp_path / "state.db")
    session_id = "session-alpha"

    try:
        db.create_session(
            session_id=session_id,
            source="cli",
            model="gpt-test",
            system_prompt="You are Motis.",
            user_id="user-123",
        )

        db.append_message(session_id, "user", "Show me BTC momentum.")
        db.append_message(
            session_id,
            "assistant",
            "BTC momentum is positive.",
            tool_calls=[{"id": "call_1", "type": "function"}],
            reasoning="Momentum summary",
            reasoning_details={"confidence": "high"},
            codex_reasoning_items=[{"type": "summary", "text": "condensed"}],
            finish_reason="stop",
            token_count=42,
        )

        session = db.get_session(session_id)
        assert session is not None
        assert session["user_id"] == "user-123"
        assert session["source"] == "cli"
        assert session["message_count"] == 2
        assert session["tool_call_count"] == 1

        messages = db.get_messages(session_id)
        assert [message["role"] for message in messages] == ["user", "assistant"]
        assert messages[1]["tool_calls"] == [{"id": "call_1", "type": "function"}]
        assert messages[1]["token_count"] == 42
        assert messages[1]["finish_reason"] == "stop"

        conversation = db.get_messages_as_conversation(session_id)
        assert conversation[1]["reasoning"] == "Momentum summary"
        assert conversation[1]["reasoning_details"] == {"confidence": "high"}
        assert conversation[1]["codex_reasoning_items"] == [
            {"type": "summary", "text": "condensed"}
        ]

        search_results = db.search_messages("BTC momentum", source_filter=["cli"])
        assert len(search_results) == 2
        assert search_results[0]["session_id"] == session_id
        assert search_results[0]["source"] == "cli"
        assert search_results[0]["context"]

        db.clear_messages(session_id)
        assert db.message_count(session_id) == 0
        cleared_session = db.get_session(session_id)
        assert cleared_session is not None
        assert cleared_session["message_count"] == 0
        assert cleared_session["tool_call_count"] == 0
    finally:
        db.close()


def test_sessiondb_readonly_mode_supports_queries_without_schema_writes(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    writable = SessionDB(db_path=db_path)
    try:
        writable.create_session("session-ro", source="cli", user_id="user-ro")
        writable.append_message("session-ro", "user", "hello")
    finally:
        writable.close()

    readonly = SessionDB(db_path=db_path, readonly=True)
    try:
        session = readonly.get_session("session-ro")
        assert session is not None
        assert session["user_id"] == "user-ro"
        messages = readonly.get_messages("session-ro")
        assert [message["content"] for message in messages] == ["hello"]
    finally:
        readonly.close()


def test_delete_session_orphans_child_conversations(tmp_path: Path) -> None:
    db = SessionDB(db_path=tmp_path / "state.db")

    try:
        db.create_session("parent-1", source="cli", user_id="user-1")
        db.create_session(
            "child-1",
            source="cli",
            user_id="user-1",
            parent_session_id="parent-1",
        )

        deleted = db.delete_session("parent-1")

        assert deleted is True
        assert db.get_session("parent-1") is None
        child = db.get_session("child-1")
        assert child is not None
        assert child["parent_session_id"] is None
    finally:
        db.close()


def test_legacy_tables_backfill_into_motis_tables_without_becoming_active_path(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "state.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version (version) VALUES (7)")
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT,
                source TEXT,
                model TEXT,
                model_config TEXT,
                system_prompt TEXT,
                parent_session_id TEXT,
                started_at REAL,
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
                pricing_version TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                tool_call_id TEXT,
                tool_calls TEXT,
                tool_name TEXT,
                timestamp REAL NOT NULL,
                finish_reason TEXT,
                reasoning TEXT,
                reasoning_details TEXT,
                codex_reasoning_items TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO sessions (
                id, user_id, title, source, model, model_config, system_prompt,
                parent_session_id, started_at, ended_at, end_reason, message_count,
                tool_call_count, input_tokens, output_tokens, cache_read_tokens,
                cache_write_tokens, reasoning_tokens, billing_provider,
                billing_base_url, billing_mode, estimated_cost_usd,
                actual_cost_usd, cost_status, cost_source, pricing_version
            ) VALUES (
                'legacy-1', 'legacy-user', 'Legacy Title', 'telegram', 'legacy-model',
                NULL, 'Legacy system prompt', NULL, 1000.0, NULL, NULL, 1, 0, 0, 0,
                0, 0, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO messages (
                id, session_id, role, content, tool_call_id, tool_calls, tool_name,
                timestamp, finish_reason, reasoning, reasoning_details,
                codex_reasoning_items
            ) VALUES (
                1, 'legacy-1', 'user', 'legacy content', NULL, NULL, NULL,
                1001.0, NULL, NULL, NULL, NULL
            )
            """
        )
        conn.commit()

    db = SessionDB(db_path=db_path)

    try:
        migrated = db.get_session("legacy-1")
        assert migrated is not None
        assert migrated["user_id"] == "legacy-user"
        assert migrated["source"] == "telegram"
        assert migrated["message_count"] == 1

        migrated_messages = db.get_messages("legacy-1")
        assert [message["content"] for message in migrated_messages] == ["legacy content"]

        db.create_session("motis-1", source="cli", user_id="motis-user")
        db.append_message("motis-1", "user", "new content")
    finally:
        db.close()

    with sqlite3.connect(db_path) as conn:
        legacy_session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        legacy_message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        conversation_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        conversation_message_count = conn.execute(
            "SELECT COUNT(*) FROM conversation_messages"
        ).fetchone()[0]

    assert legacy_session_count == 1
    assert legacy_message_count == 1
    assert conversation_count == 2
    assert conversation_message_count == 2
