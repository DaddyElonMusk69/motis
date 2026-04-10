"""
Motis Agent Loop
================
Adapted from NousResearch/hermes-agent run_agent.py (MIT License)
Original: https://github.com/NousResearch/hermes-agent

Key adaptations vs. Hermes AIAgent:
- Stateless per-request: no global state, no filesystem config
- UserContext injected at construction: memory, skills, operators, model config
- Async generator (stream_conversation) yields SSE-ready event dicts
- No print() anywhere — all output goes through the event stream
- No CLI entrypoint, no gateway code, no Telegram/Discord
- Tool registry is built from UserContext, not global toolset config
- SubagentRunner replaces Hermes's delegate_tool AIAgent spawn -- shares UserContext
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from motis_agent.context import UserContext

logger = logging.getLogger(__name__)


# ── SSE event types (consumed by services/agent/motis_agent/server.py) ──────
# All events are JSON-serialisable dicts with at minimum {"type": str, "ts": float}

EVENT_TYPES = {
    "message_start",      # Agent starts processing a user message
    "thinking",           # Reasoning / thinking text (extended thinking models)
    "tool_call",          # Agent is calling a tool  {"tool": str, "args": dict}
    "tool_result",        # Tool returned a result   {"tool": str, "result": any, "ok": bool}
    "text_delta",         # Streaming text chunk     {"text": str}
    "message_end",        # Agent loop complete      {"stop_reason": str}
    "error",              # Unrecoverable error      {"message": str}
    "subagent_progress",  # Sub-agent activity relay {"agent_index": int, "tool": str}
}


def _event(type_: str, **kwargs) -> dict:
    return {"type": type_, "ts": time.time(), **kwargs}


# ── Tool registry ────────────────────────────────────────────────────────────
# Tools available to the master agent. Built at loop construction time from
# UserContext (so tool availability can vary per user / per conversation).

def _build_tool_definitions(ctx: UserContext) -> list[dict]:
    """
    Build the OpenAI tool_choice definitions list for this user's session.

    Order matters for model attention — put high-priority tools first.
    Finance skills are exposed as individual tools (auto-discovered from
    the skill registry). MCP tools (operator_*, execute_*) are included
    when the user has at least one connected exchange.
    """
    from motis_agent.tools._registry import get_tool_definitions

    tools = []

    # Core agent tools (always available)
    tools.extend(get_tool_definitions([
        "memory_add",
        "memory_search",
        "memory_recall",
        "web_search",
        "web_fetch",
        "delegate_task",
        "mixture_of_agents",
    ]))

    # Terminal tool (sandboxed Python execution) — always included
    tools.extend(get_tool_definitions(["terminal"]))

    # Callable domain skills (currently finance-only, via SkillRegistry)
    tools.extend(ctx.skill_registry.get_tool_definitions())

    # MCP operator tools — always included (user may not have operators yet, that's fine)
    tools.extend(get_tool_definitions([
        "operator_create",
        "operator_list",
        "operator_invoke",
        "operator_status",
        "operator_pause",
        "operator_archive",
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

    MAX_TURNS = 40          # Guard against infinite tool loops
    MAX_SUB_DEPTH = 2       # Sub-agents cannot spawn grandchildren

    def __init__(self, ctx: UserContext, *, sub_depth: int = 0):
        self.ctx = ctx
        self.sub_depth = sub_depth  # 0 = master agent, 1 = sub-agent

        # Build async OpenAI client from user's BYOM config
        model_cfg = ctx.model_config
        self.client = AsyncOpenAI(
            api_key=model_cfg.api_key,
            base_url=model_cfg.base_url,
        )
        self.model = model_cfg.model

        # Build tool definitions once per loop instance
        self._tools = _build_tool_definitions(ctx)
        self._tool_names = {t["function"]["name"] for t in self._tools}

        # Conversation messages (accumulates across turns)
        self._messages: list[dict] = []

        # Load user memory into system prompt context
        self._system_prompt: str | None = None  # built lazily on first call

    # ── System prompt ─────────────────────────────────────────────────────────

    async def _build_system_prompt(self) -> str:
        """
        Build the system prompt for this user's session.
        Adapted from Hermes agent/prompt_builder.py:build_skills_system_prompt.

        Includes:
        - Agent identity (Motis-specific)
        - User's memory context (recent memories, strategy preferences)
        - Available operator list + their current state
        - Finance skill catalogue summary
        - Platform hints (web SSE, no filesystem)
        """
        from motis_agent.core.prompts import build_motis_system_prompt
        memory_ctx = await self.ctx.memory.get_context_block()
        operator_ctx = await self.ctx.operator_registry.get_context_block()
        return build_motis_system_prompt(
            user_ctx=self.ctx,
            memory_block=memory_ctx,
            operator_block=operator_ctx,
        )

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
        - Removed max_iterations shared budget (each request has its own MAX_TURNS)
        - Removed trajectory saving (future: save to DB via ctx)
        """
        yield _event("message_start", conversation_id=self.ctx.conversation_id)

        # Build system prompt on first turn
        if self._system_prompt is None:
            self._system_prompt = await self._build_system_prompt()

        # Append user message
        self._messages.append({"role": "user", "content": user_message})

        turns = 0
        while turns < self.MAX_TURNS:
            turns += 1

            # ── LLM call ──────────────────────────────────────────────────────
            try:
                response_text, tool_calls, stop_reason = await self._call_model()
            except Exception as exc:
                logger.error("Model call failed: %s", exc, exc_info=True)
                yield _event("error", message=f"Model error: {exc}")
                return

            # ── Stream text delta ──────────────────────────────────────────────
            if response_text:
                yield _event("text_delta", text=response_text)

            # ── No tool calls → agent is done ─────────────────────────────────
            if not tool_calls:
                self._messages.append({
                    "role": "assistant",
                    "content": response_text or "",
                })
                # Persist memory snippets from this turn
                await self._maybe_save_memory(response_text)
                yield _event("message_end", stop_reason=stop_reason)
                return

            # ── Has tool calls → execute and loop ─────────────────────────────
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": response_text}
            assistant_msg["tool_calls"] = tool_calls
            self._messages.append(assistant_msg)

            tool_results = await self._execute_tool_calls(tool_calls)

            for event in tool_results["events"]:
                yield event

            self._messages.extend(tool_results["messages"])

        # Exceeded MAX_TURNS
        yield _event("message_end", stop_reason="max_turns_exceeded")

    # ── Model call ────────────────────────────────────────────────────────────

    async def _call_model(self) -> tuple[str, list, str]:
        """
        Make one API call to the model.
        Returns (response_text, tool_calls, stop_reason).

        Adapted from Hermes AIAgent._call_api():
        - Async instead of sync
        - No prompt caching (add later when we know which providers support it)
        - No reasoning/thinking extraction yet (add per-provider adapter later)
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                *self._messages,
            ],
            tools=self._tools,
            tool_choice="auto",
        )

        choice = response.choices[0]
        stop_reason = choice.finish_reason  # "stop", "tool_calls", "length"

        response_text = ""
        if choice.message.content:
            response_text = choice.message.content

        tool_calls = []
        if choice.message.tool_calls:
            tool_calls = choice.message.tool_calls

        return response_text, tool_calls, stop_reason

    # ── Tool execution ────────────────────────────────────────────────────────

    async def _execute_tool_calls(
        self, tool_calls: list
    ) -> dict:
        """
        Execute a batch of tool calls (potentially in parallel for safe tools).
        Returns {"events": [event_dict, ...], "messages": [tool_msg, ...]}.

        Adapted from Hermes AIAgent._handle_tool_calls():
        - All tool calls are dispatched via MotisToolRouter
        - Safe tools (web_search, memory_search, finance.*) run in parallel
        - Stateful tools (execute_*, operator_invoke, terminal) run sequentially
        - Sub-agent delegation runs via SubagentRunner with shared UserContext
        """
        from motis_agent.tools._router import MotisToolRouter
        router = MotisToolRouter(self.ctx, sub_depth=self.sub_depth)

        events: list[dict] = []
        messages: list[dict] = []

        for tc in tool_calls:
            tool_name = tc.function.name
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
