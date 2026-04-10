"""
Built-in Postgres memory provider for Motis.

This provider wraps the existing MemoryStore so the runtime can depend on a
Hermes-style provider/manager architecture without reintroducing Hermes storage
patterns or filesystem state.
"""

from __future__ import annotations

from typing import Any

from motis_agent.core.memory import MemoryEntry, MemoryStore
from motis_agent.core.memory_provider import MemoryProvider


class PostgresMemoryProvider(MemoryProvider):
    """Motis-owned built-in memory provider backed by Postgres."""

    _TOOL_NAMES = ("memory_add", "memory_search", "memory_recall")

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "postgres_builtin"

    async def system_prompt_block(self) -> str:
        return await self._store.get_context_block()

    async def prefetch(self, query: str, **kwargs: Any) -> str:
        if not query or len(query.strip()) < 2:
            return ""

        entries = await self._store.search(
            query=query,
            limit=self._store.CONTEXT_BLOCK_LIMIT,
        )
        return self._format_entries(entries)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        from motis_agent.tools._registry import get_tool_definitions

        return get_tool_definitions(list(self._TOOL_NAMES))

    async def handle_tool_call(self, tool_name: str, args: dict[str, Any], **kwargs: Any) -> Any:
        if tool_name == "memory_add":
            memory_id = await self._store.add(
                content=args.get("content", ""),
                type=args.get("type", "general"),
                importance=int(args.get("importance", 5)),
            )
            return {"ok": True, "memory_id": str(memory_id)}

        if tool_name == "memory_search":
            results = await self._store.search(
                query=args.get("query", ""),
                limit=int(args.get("limit", 8)),
            )
            return {"results": [entry.model_dump() for entry in results]}

        if tool_name == "memory_recall":
            results = await self._store.recent(limit=int(args.get("limit", 20)))
            return {"results": [entry.model_dump() for entry in results]}

        raise ValueError(f"Unsupported memory tool for {self.name}: {tool_name}")

    def _format_entries(self, entries: list[MemoryEntry]) -> str:
        if not entries:
            return ""

        lines: list[str] = []
        total_chars = 0
        for entry in entries:
            line = f"[{entry.type.upper()}] {entry.content}"
            if total_chars + len(line) > self._store.MAX_CONTEXT_CHARS:
                lines.append("... (truncated)")
                break
            lines.append(line)
            total_chars += len(line)

        return "\n".join(lines)
