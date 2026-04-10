"""
Motis Agent Runtime
===================
Adapted from NousResearch/hermes-agent run_agent.py (MIT License)
Original: https://github.com/NousResearch/hermes-agent

Key adaptations vs. Hermes AIAgent:
- Stateless per-request: no global state, no filesystem config
- UserContext injected at construction: memory, skills, operators, model config
- Async generator (stream_conversation) yields SSE-ready event dicts
- No print() anywhere — all output goes through the event stream
- No CLI entrypoint, no gateway code, no Telegram/Discord
- Tool registry is built from UserContext, not global toolset config
- SubagentRunner replaces Hermes's delegate_tool AIAgent spawn -- child conversations are isolated
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from typing import Any, AsyncGenerator

from motis_agent.context import UserContext
from motis_agent.core.auxiliary_client import AuxiliarySummaryClient
from motis_agent.core.budget import IterationBudget
from motis_agent.core.compression import CompactionRegion, ContextCompressor
from motis_agent.core.provider_runtime import ProviderRuntime
from motis_agent.core.runtime_events import EVENT_TYPES, make_runtime_event

logger = logging.getLogger(__name__)


def _event(type_: str, **kwargs) -> dict:
    return make_runtime_event(type_, **kwargs)


# ── Tool registry ────────────────────────────────────────────────────────────
# Tools available to the master agent. Built at loop construction time from
# UserContext (so tool availability can vary per user / per conversation).

def _build_tool_definitions(ctx: UserContext) -> list[dict]:
    """
    Build the OpenAI tool_choice definitions list for this user's session.

    Order matters for model attention — put high-priority tools first.
    Finance skills and operator tools are exposed as local Motis primitives.
    Only remote execution tools stay behind the MCP boundary.
    """
    from motis_agent.tools._registry import get_tool_definitions

    tools = []

    # Provider-owned memory tools come from the memory manager.
    tools.extend(ctx.memory_manager.get_all_tool_definitions())

    # Core agent tools (always available)
    tools.extend(get_tool_definitions([
        "session_search",
        "web_search",
        "web_fetch",
        "delegate_task",
        "mixture_of_agents",
    ]))

    # Terminal tool (sandboxed Python execution) — always included
    tools.extend(get_tool_definitions(["terminal"]))

    # Callable domain skills (currently finance-only, via SkillRegistry)
    tools.extend(ctx.skill_registry.get_tool_definitions())

    # Local operator tools — always included (user may not have operators yet, that's fine)
    tools.extend(get_tool_definitions([
        "operator_create",
        "operator_list",
        "operator_invoke",
        "operator_status",
        "operator_pause",
        "operator_archive",
        "operator_update_prompt",
        "operator_export",
    ]))

    # MCP trading execution tools — only if user has a connected exchange
    if ctx.has_connected_exchange:
        tools.extend(get_tool_definitions([
            "execute_paper_trade",
            "execute_live_trade",
            "get_positions",
        ]))

    return tools


# ── MotisAgentLoop ────────────────────────────────────────────────────────────

class MotisAgentLoop:
    """
    Stateless-per-request ReAct agent loop for the Motis Master Agent.

    One instance per HTTP request. Constructed with a UserContext that provides
    per-user memory, skill registry, model config, and operator registry.

    Usage (in server.py):
        loop = MotisAgentLoop(ctx)
        async for event in loop.stream(user_message):
            yield f"data: {json.dumps(event)}\\n\\n"
    """

    MAX_TURNS = 40          # Per-loop cap (guard against infinite tool loops)
    MAX_SUB_DEPTH = 2       # Sub-agents cannot spawn grandchildren

    def __init__(
        self,
        ctx: UserContext,
        *,
        sub_depth: int = 0,
        max_turns: int | None = None,
        iteration_budget: IterationBudget | None = None,
    ):
        self.ctx = ctx
        self.sub_depth = sub_depth  # 0 = master agent, 1 = sub-agent
        self.max_turns = int(max_turns or self.MAX_TURNS)
        if self.max_turns < 1:
            self.max_turns = 1
        self.iteration_budget = iteration_budget or IterationBudget(self.max_turns)

        # Motis-owned provider runtime (API mode, retries, error taxonomy).
        self.provider_runtime = ProviderRuntime(ctx.model_config)
        self.model = self.provider_runtime.model
        self.context_compressor = ContextCompressor(
            context_length=self.provider_runtime.capabilities.context_length
        )
        self.auxiliary_summary_client = AuxiliarySummaryClient.from_model_config(ctx.model_config)

        # Build tool definitions once per loop instance
        self._tools = _build_tool_definitions(ctx)
        self._tool_names = {t["function"]["name"] for t in self._tools}

        # Conversation messages (accumulates across turns)
        self._messages: list[dict] = []
        self._session_loaded_count = 0
        self._session_persisted_count = 0

        # Prompt layering: stable cached core + session overlays + turn overlays.
        self._cached_prompt_messages: list[dict[str, str]] = []
        self._session_prompt_messages: list[dict[str, str]] = []
        self._turn_prompt_messages: list[dict[str, str]] = []

    # ── System prompt ─────────────────────────────────────────────────────────

    async def _build_prompt_layers(self) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """
        Build cached and session-scoped prompt layers for this user's session.

        Cached core:
        - agent identity
        - platform/tool guidance
        - model-family execution guidance

        Session overlays:
        - durable memory block
        - current operator block
        - conversation/session metadata
        """
        from motis_agent.core.prompts import build_motis_prompt_assembly
        memory_ctx = await self.ctx.memory_manager.build_system_prompt()
        operator_ctx = await self.ctx.operator_registry.get_context_block()
        assembly = build_motis_prompt_assembly(
            user_ctx=self.ctx,
            memory_block=memory_ctx,
            operator_block=operator_ctx,
        )
        return assembly.cached_messages(), assembly.session_messages()

    # ── Main stream entrypoint ─────────────────────────────────────────────────

    async def stream(
        self, user_message: str
    ) -> AsyncGenerator[dict, None]:
        """
        Process one user message through the ReAct loop.
        Yields SSE event dicts until the agent produces a final response or errors.

        Adapted from Hermes AIAgent.run_conversation():
        - Replaced print() with yield _event(...)
        - Replaced blocking OpenAI client with async client
        - Uses a Motis IterationBudget so parent/child loops can share a global turn cap
        - Removed trajectory saving (future: save to DB via ctx)
        """
        yield _event("message_start", conversation_id=self.ctx.conversation_id)

        await self._hydrate_session_history(user_message)

        try:
            # Build prompt layers on first turn
            if not self._cached_prompt_messages:
                (
                    self._cached_prompt_messages,
                    self._session_prompt_messages,
                ) = await self._build_prompt_layers()
            turn_memory_context = await self.ctx.memory_manager.build_prefetch_context(
                user_message,
                conversation_id=self.ctx.conversation_id,
            )
            self._turn_prompt_messages = self._build_turn_prompt_messages(
                memory_context=turn_memory_context,
            )
            self._messages.append({"role": "user", "content": user_message})

            turns = 0
            while turns < self.max_turns:
                has_budget = await self.iteration_budget.try_consume(1)
                if not has_budget:
                    yield _event("message_end", stop_reason="iteration_budget_exhausted")
                    return
                turns += 1
                remaining_turns = await self.iteration_budget.remaining()
                yield _event(
                    "budget_update",
                    turn=turns,
                    remaining_turns=remaining_turns,
                    max_turns=self.max_turns,
                    sub_depth=self.sub_depth,
                )
                await self.ctx.memory_manager.on_turn_start(
                    turns,
                    user_message,
                    conversation_id=self.ctx.conversation_id,
                    model=self.model,
                    tool_count=len(self._tools),
                )

                # ── LLM call ──────────────────────────────────────────────────
                try:
                    (
                        response_text,
                        tool_calls,
                        stop_reason,
                        preflight_event,
                    ) = await self._call_model()
                    if preflight_event is not None:
                        yield _event("context_compaction", **preflight_event)
                except Exception as exc:
                    logger.error("Model call failed: %s", exc, exc_info=True)
                    yield _event("error", message=f"Model error: {exc}")
                    return

                # ── Stream text delta ─────────────────────────────────────────
                if response_text:
                    yield _event("text_delta", text=response_text)

                # ── No tool calls → agent is done ────────────────────────────
                if not tool_calls:
                    self._messages.append({
                        "role": "assistant",
                        "content": response_text or "",
                    })
                    await self.ctx.memory_manager.sync_all(
                        user_message,
                        response_text or "",
                        conversation_id=self.ctx.conversation_id,
                    )
                    await self.ctx.memory_manager.queue_prefetch_all(
                        user_message,
                        conversation_id=self.ctx.conversation_id,
                    )
                    # Persist memory snippets from this turn
                    await self._maybe_save_memory(response_text)
                    yield _event("message_end", stop_reason=stop_reason)
                    return

                # ── Has tool calls → execute and loop ────────────────────────
                assistant_msg: dict[str, Any] = {"role": "assistant", "content": response_text}
                assistant_msg["tool_calls"] = [self._jsonable_tool_call(tc) for tc in tool_calls]
                self._messages.append(assistant_msg)

                tool_results = await self._execute_tool_calls(tool_calls)

                for event in tool_results["events"]:
                    yield event

                self._messages.extend(tool_results["messages"])

            # Exceeded per-loop max turns
            yield _event("message_end", stop_reason="max_turns_exceeded")
        finally:
            await self._flush_session_messages()

    # ── Model call ────────────────────────────────────────────────────────────

    async def _call_model(self) -> tuple[str, list, str, dict[str, Any] | None]:
        """
        Make one API call to the model.
        Returns (response_text, tool_calls, stop_reason, preflight_event).

        Adapted from Hermes AIAgent._call_api():
        - Async instead of sync
        - No prompt caching (add later when we know which providers support it)
        - No reasoning/thinking extraction yet (add per-provider adapter later)
        """
        model_messages, preflight_event = await self._build_model_messages_with_preflight()
        result = await self.provider_runtime.chat_completion(
            messages=model_messages,
            tools=self._tools,
            tool_choice="auto",
        )

        return result.text, result.tool_calls, result.stop_reason, preflight_event

    async def _build_model_messages_with_preflight(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """
        Build model input messages and run deterministic context compaction
        preflight when the prompt is near the context limit.

        If middle-region collapse was used, optionally enrich the deterministic
        recap with an auxiliary-model summary. Failures always fall back to
        deterministic compaction output.
        """
        model_messages = self._build_model_messages()
        compression = self.context_compressor.compress(model_messages)
        if not compression.changed:
            return model_messages, None

        compressed_messages = compression.messages
        summary_applied = False
        summary_model: str | None = None
        compacted_turns = 0
        if compression.compaction_region is not None:
            compacted_turns = len(compression.compaction_region.compacted_messages)
            (
                compressed_messages,
                summary_applied,
                summary_model,
            ) = await self._maybe_enrich_compaction_summary(
                compressed_messages,
                compression.compaction_region,
            )

        stats = compression.stats
        final_compressed_tokens = self.context_compressor.estimate_tokens(compressed_messages)
        event_payload: dict[str, Any] = {
            "original_tokens": stats.original_tokens,
            "compressed_tokens": final_compressed_tokens,
            "threshold_tokens": stats.threshold_tokens,
            "context_length": stats.context_length,
            "original_messages": stats.original_messages,
            "compressed_messages": stats.compressed_messages,
            "dropped_messages": stats.dropped_messages,
            "pruned_tool_results": stats.pruned_tool_results,
            "strategy": stats.strategy,
            "sub_depth": self.sub_depth,
            "compacted_turns": compacted_turns,
            "summary_applied": summary_applied,
        }
        if summary_model:
            event_payload["summary_model"] = summary_model
        return compressed_messages, event_payload

    async def _maybe_enrich_compaction_summary(
        self,
        messages: list[dict[str, Any]],
        region: CompactionRegion,
    ) -> tuple[list[dict[str, Any]], bool, str | None]:
        client = self.auxiliary_summary_client
        summary_index = region.summary_index
        if client is None or summary_index is None:
            return messages, False, None
        if summary_index < 0 or summary_index >= len(messages):
            return messages, False, None

        summary_message = messages[summary_index]
        if str(summary_message.get("role") or "") != "system":
            return messages, False, None

        deterministic_summary = str(summary_message.get("content") or "").strip()
        if not deterministic_summary:
            return messages, False, None

        try:
            enriched_summary = await client.summarize_compaction(
                compacted_messages=region.compacted_messages,
                deterministic_summary=deterministic_summary,
            )
        except Exception as exc:
            logger.warning("Auxiliary compaction summary failed: %s", exc)
            return messages, False, None

        if not enriched_summary:
            return messages, False, None

        patched = [copy.deepcopy(msg) for msg in messages]
        patched[summary_index]["content"] = enriched_summary
        patched_tokens = self.context_compressor.estimate_tokens(patched)
        if patched_tokens > self.context_compressor.threshold_tokens:
            logger.warning(
                "Skipping auxiliary summary replacement: enriched prompt exceeded threshold (%s > %s)",
                patched_tokens,
                self.context_compressor.threshold_tokens,
            )
            return messages, False, None
        return patched, True, client.model

    def _build_model_messages(self) -> list[dict[str, Any]]:
        """
        Assemble the model input messages for the current turn.
        Query-specific recalled memory and session context are injected as
        separate overlays so they stay distinct from the cached core prompt
        and from user content.
        """
        messages: list[dict[str, Any]] = []
        messages.extend(copy.deepcopy(self._cached_prompt_messages))
        messages.extend(copy.deepcopy(self._session_prompt_messages))
        messages.extend(copy.deepcopy(self._turn_prompt_messages))
        messages.extend(self._messages)
        return messages

    def _build_turn_prompt_messages(self, *, memory_context: str) -> list[dict[str, str]]:
        from motis_agent.core.prompts import build_turn_prompt_layers

        return [
            layer.to_message()
            for layer in build_turn_prompt_layers(memory_context=memory_context)
        ]

    async def _hydrate_session_history(self, user_message: str) -> None:
        """
        Ensure the conversation exists and load any previously persisted
        messages so repeated requests with the same conversation_id replay
        prior turns.
        """
        await self.ctx.session_store.ensure_conversation(seed_title=user_message)
        history = await self.ctx.session_store.get_messages_as_conversation()
        self._messages = list(history)
        self._session_loaded_count = len(history)
        self._session_persisted_count = len(history)

    async def _flush_session_messages(self) -> None:
        """
        Persist only the new messages produced during this request.
        Safe to call multiple times.
        """
        new_messages = self._messages[self._session_persisted_count :]
        if not new_messages:
            return
        try:
            inserted = await self.ctx.session_store.append_messages(new_messages)
        except Exception as exc:
            logger.error("Failed to persist conversation %s: %s", self.ctx.conversation_id, exc, exc_info=True)
            return
        self._session_persisted_count += inserted

    def _jsonable_tool_call(self, tool_call: Any) -> dict[str, Any]:
        if hasattr(tool_call, "model_dump"):
            return tool_call.model_dump()
        if isinstance(tool_call, dict):
            return tool_call
        return {
            "id": getattr(tool_call, "id", ""),
            "type": getattr(tool_call, "type", "function"),
            "function": {
                "name": getattr(getattr(tool_call, "function", None), "name", ""),
                "arguments": getattr(getattr(tool_call, "function", None), "arguments", "{}"),
            },
        }

    # ── Tool execution ────────────────────────────────────────────────────────

    async def _execute_tool_calls(
        self, tool_calls: list
    ) -> dict:
        """
        Execute a batch of tool calls (potentially in parallel for safe tools).
        Returns {"events": [event_dict, ...], "messages": [tool_msg, ...]}.

        Adapted from Hermes AIAgent._handle_tool_calls():
        - All tool calls are dispatched via MotisToolRouter
        - Safe tools (session_search, web_search, memory_search, finance.*) can later run in parallel
        - Stateful tools (execute_*, operator_invoke, terminal) run sequentially
        - Sub-agent delegation runs via SubagentRunner with shared UserContext
        """
        from motis_agent.tools._router import MotisToolRouter
        events: list[dict] = []
        messages: list[dict] = []
        active_parent_tool = ""
        active_parent_call_id = ""

        async def _on_subagent_progress(payload: dict[str, Any]) -> None:
            events.append(
                _event(
                    "subagent_progress",
                    parent_tool=active_parent_tool,
                    parent_call_id=active_parent_call_id,
                    **payload,
                )
            )

        router = MotisToolRouter(
            self.ctx,
            sub_depth=self.sub_depth,
            iteration_budget=self.iteration_budget,
            progress_callback=_on_subagent_progress,
        )

        for tc in tool_calls:
            tool_name = tc.function.name
            active_parent_tool = tool_name
            active_parent_call_id = tc.id
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            yield_event = _event("tool_call", tool=tool_name, args=args, call_id=tc.id)
            events.append(yield_event)

            try:
                result = await router.dispatch(tool_name, args, call_id=tc.id)
                ok = True
            except Exception as exc:
                logger.error("Tool %s failed: %s", tool_name, exc, exc_info=True)
                result = {"error": str(exc)}
                ok = False

            events.append(_event(
                "tool_result",
                tool=tool_name,
                result=result,
                ok=ok,
                call_id=tc.id,
            ))

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result) if not isinstance(result, str) else result,
            })

        return {"events": events, "messages": messages}

    # ── Memory persistence ─────────────────────────────────────────────────────

    async def _maybe_save_memory(self, response_text: str) -> None:
        """
        Extract memory-worthy content from the agent's final response and save.
        Adapted from Hermes agent/memory_manager.py:on_turn_complete().

        Hermes saves to MEMORY.md (filesystem). We save to PostgreSQL
        via ctx.memory.add() which is scoped to ctx.user_id.
        """
        if not response_text or len(response_text) < 100:
            return
        # TODO: implement lightweight memory extraction (Phase 0 stub)
        # Will call ctx.memory.add(content=..., type="agent_insight")
        pass
