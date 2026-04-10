"""
Motis Memory Manager
====================

Async orchestration layer over one or more Motis memory providers.
Adapted from Hermes's MemoryManager, but scoped to Motis's request-driven,
Postgres-backed runtime.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from motis_agent.core.memory_provider import MemoryProvider, build_memory_context_block

logger = logging.getLogger(__name__)


class MemoryManager:
    """Coordinates memory providers and routes provider-owned memory tools."""

    def __init__(self, providers: list[MemoryProvider] | None = None) -> None:
        self._providers: list[MemoryProvider] = []
        self._tool_to_provider: dict[str, MemoryProvider] = {}

        for provider in providers or []:
            self.add_provider(provider)

    def add_provider(self, provider: MemoryProvider) -> None:
        """Register a provider and index its tool ownership."""
        self._providers.append(provider)

        for definition in provider.get_tool_definitions():
            function = definition.get("function") or {}
            name = function.get("name")
            if not name:
                continue
            if name in self._tool_to_provider:
                logger.warning(
                    "Memory tool name conflict: %s already owned by %s; ignoring duplicate from %s",
                    name,
                    self._tool_to_provider[name].name,
                    provider.name,
                )
                continue
            self._tool_to_provider[name] = provider

    @property
    def providers(self) -> list[MemoryProvider]:
        return list(self._providers)

    def get_provider(self, name: str) -> MemoryProvider | None:
        for provider in self._providers:
            if provider.name == name:
                return provider
        return None

    async def build_system_prompt(self) -> str:
        """Collect provider-contributed memory prompt blocks."""
        blocks: list[str] = []
        for provider in self._providers:
            try:
                block = await provider.system_prompt_block()
            except Exception as exc:
                logger.warning(
                    "Memory provider %s system_prompt_block() failed: %s",
                    provider.name,
                    exc,
                )
                continue

            if block and block.strip():
                blocks.append(block.strip())

        return "\n\n".join(blocks)

    async def build_prefetch_context(
        self,
        query: str,
        *,
        conversation_id: UUID | None = None,
    ) -> str:
        """
        Recall provider context for the upcoming model call and wrap it in a
        fenced block so it stays separate from fresh user input.
        """
        parts: list[str] = []
        for provider in self._providers:
            try:
                part = await provider.prefetch(query, conversation_id=conversation_id)
            except Exception as exc:
                logger.debug(
                    "Memory provider %s prefetch failed (non-fatal): %s",
                    provider.name,
                    exc,
                )
                continue

            if part and part.strip():
                parts.append(part.strip())

        return build_memory_context_block("\n\n".join(parts))

    async def queue_prefetch_all(
        self,
        query: str,
        *,
        conversation_id: UUID | None = None,
    ) -> None:
        for provider in self._providers:
            try:
                await provider.queue_prefetch(query, conversation_id=conversation_id)
            except Exception as exc:
                logger.debug(
                    "Memory provider %s queue_prefetch() failed (non-fatal): %s",
                    provider.name,
                    exc,
                )

    async def sync_all(
        self,
        user_content: str,
        assistant_content: str,
        *,
        conversation_id: UUID | None = None,
    ) -> None:
        for provider in self._providers:
            try:
                await provider.sync_turn(
                    user_content,
                    assistant_content,
                    conversation_id=conversation_id,
                )
            except Exception as exc:
                logger.warning(
                    "Memory provider %s sync_turn() failed: %s",
                    provider.name,
                    exc,
                )

    def get_all_tool_definitions(self) -> list[dict[str, Any]]:
        """Return deduplicated provider-owned tool definitions."""
        definitions: list[dict[str, Any]] = []
        seen: set[str] = set()

        for provider in self._providers:
            for definition in provider.get_tool_definitions():
                function = definition.get("function") or {}
                name = function.get("name")
                if not name or name in seen:
                    continue
                definitions.append(definition)
                seen.add(name)

        return definitions

    def get_all_tool_names(self) -> set[str]:
        return set(self._tool_to_provider)

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self._tool_to_provider

    async def handle_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        provider = self._tool_to_provider.get(tool_name)
        if provider is None:
            raise ValueError(f"No memory provider handles tool {tool_name!r}")
        return await provider.handle_tool_call(tool_name, args, **kwargs)

    async def on_turn_start(self, turn_number: int, message: str, **kwargs: Any) -> None:
        for provider in self._providers:
            try:
                await provider.on_turn_start(turn_number, message, **kwargs)
            except Exception as exc:
                logger.debug(
                    "Memory provider %s on_turn_start() failed (non-fatal): %s",
                    provider.name,
                    exc,
                )

    async def on_session_end(self, messages: list[dict[str, Any]]) -> None:
        for provider in self._providers:
            try:
                await provider.on_session_end(messages)
            except Exception as exc:
                logger.debug(
                    "Memory provider %s on_session_end() failed (non-fatal): %s",
                    provider.name,
                    exc,
                )

    async def on_pre_compress(self, messages: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for provider in self._providers:
            try:
                part = await provider.on_pre_compress(messages)
            except Exception as exc:
                logger.debug(
                    "Memory provider %s on_pre_compress() failed (non-fatal): %s",
                    provider.name,
                    exc,
                )
                continue

            if part and part.strip():
                parts.append(part.strip())

        return "\n\n".join(parts)

    async def on_delegation(
        self,
        task: str,
        result: str,
        *,
        child_session_id: str = "",
        **kwargs: Any,
    ) -> None:
        for provider in self._providers:
            try:
                await provider.on_delegation(
                    task,
                    result,
                    child_session_id=child_session_id,
                    **kwargs,
                )
            except Exception as exc:
                logger.debug(
                    "Memory provider %s on_delegation() failed (non-fatal): %s",
                    provider.name,
                    exc,
                )

    async def on_memory_write(self, action: str, target: str, content: str) -> None:
        for provider in self._providers:
            try:
                await provider.on_memory_write(action, target, content)
            except Exception as exc:
                logger.debug(
                    "Memory provider %s on_memory_write() failed (non-fatal): %s",
                    provider.name,
                    exc,
                )

    async def shutdown_all(self) -> None:
        for provider in reversed(self._providers):
            try:
                await provider.shutdown()
            except Exception as exc:
                logger.warning(
                    "Memory provider %s shutdown() failed: %s",
                    provider.name,
                    exc,
                )
