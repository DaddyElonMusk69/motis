"""
Motis Tool Router
=================
Dispatches tool calls from MotisAgentLoop to the appropriate handler.

Two dispatch paths:
1. Native tools (finance skills, memory, web, terminal, subagent, moa)
   → imported and called directly in-process
2. MCP tools (operator_*, execute_*, get_positions)
   → forwarded via HTTP to the Motis MCP server

Adapted from Hermes model_tools.py:handle_function_call()
Key difference: no process-global tool registry — tools are resolved
per-request from UserContext.
"""

from __future__ import annotations

import logging
from typing import Any

from motis_agent.context import UserContext

logger = logging.getLogger(__name__)


# Tools dispatched via MCP HTTP (services/mcp)
_MCP_TOOLS = frozenset({
    "operator_create",
    "operator_list",
    "operator_invoke",
    "operator_status",
    "operator_pause",
    "operator_archive",
    "execute_paper_trade",
    "execute_live_trade",
    "get_positions",
})

# Tools that run sequentially (stateful / side-effecting)
_SEQUENTIAL_TOOLS = frozenset({
    "terminal",
    "execute_paper_trade",
    "execute_live_trade",
    "operator_invoke",
    "memory_add",
})


class MotisToolRouter:
    """
    Per-request tool dispatcher.

    Adapts Hermes's process-global handle_function_call() to a stateless,
    per-request, UserContext-scoped dispatch model.
    """

    def __init__(self, ctx: UserContext, *, sub_depth: int = 0):
        self.ctx = ctx
        self.sub_depth = sub_depth

    async def dispatch(self, tool_name: str, args: dict, *, call_id: str) -> Any:
        """
        Dispatch a single tool call. Returns a JSON-serialisable result.
        Raises on tool error (caller converts to tool_result error event).
        """
        if tool_name in _MCP_TOOLS:
            return await self._dispatch_mcp(tool_name, args)

        return await self._dispatch_native(tool_name, args)

    # ── MCP dispatch ─────────────────────────────────────────────────────────

    async def _dispatch_mcp(self, tool_name: str, args: dict) -> Any:
        """
        Forward tool call to the Motis MCP HTTP server.
        Injects user context headers so the MCP layer can enforce risk guards
        and inject the correct exchange API keys.
        """
        import httpx
        from motis_agent.settings import settings

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.mcp_url}/tools/{tool_name}",
                json=args,
                headers={
                    "X-User-Id": str(self.ctx.user_id),
                    "X-Conversation-Id": str(self.ctx.conversation_id),
                    # The MCP server verifies this token to authenticate the agent service
                    "X-Agent-Token": settings.agent_mcp_secret,
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── Native dispatch ───────────────────────────────────────────────────────

    async def _dispatch_native(self, tool_name: str, args: dict) -> Any:
        """
        Route to native tool handlers (in-process, no network hop).
        """
        # Memory tools
        if tool_name == "memory_add":
            return await self._handle_memory_add(args)
        if tool_name == "memory_search":
            return await self._handle_memory_search(args)
        if tool_name == "memory_recall":
            return await self._handle_memory_recall(args)

        # Web tools (adapted from Hermes tools/web_tools.py)
        if tool_name == "web_search":
            return await self._handle_web_search(args)
        if tool_name == "web_fetch":
            return await self._handle_web_fetch(args)

        # Terminal (sandboxed Python execution)
        if tool_name == "terminal":
            return await self._handle_terminal(args)

        # Sub-agent delegation (adapted from Hermes tools/delegate_tool.py)
        if tool_name == "delegate_task":
            return await self._handle_delegate(args)

        # Mixture-of-Agents (adapted from Hermes tools/mixture_of_agents_tool.py)
        if tool_name == "mixture_of_agents":
            return await self._handle_moa(args)

        # Finance skills (auto-routed by prefix)
        if tool_name.startswith("finance.") or tool_name.startswith("smc.") or tool_name.startswith("data."):
            return await self._handle_finance_skill(tool_name, args)

        raise ValueError(f"Unknown tool: {tool_name!r}")

    # ── Memory handlers ───────────────────────────────────────────────────────

    async def _handle_memory_add(self, args: dict) -> dict:
        content = args.get("content", "")
        mem_type = args.get("type", "general")
        memory_id = await self.ctx.memory.add(content=content, type=mem_type)
        return {"ok": True, "memory_id": str(memory_id)}

    async def _handle_memory_search(self, args: dict) -> dict:
        query = args.get("query", "")
        limit = int(args.get("limit", 10))
        results = await self.ctx.memory.search(query=query, limit=limit)
        return {"results": [r.model_dump() for r in results]}

    async def _handle_memory_recall(self, args: dict) -> dict:
        limit = int(args.get("limit", 20))
        results = await self.ctx.memory.recent(limit=limit)
        return {"results": [r.model_dump() for r in results]}

    # ── Web handlers ──────────────────────────────────────────────────────────

    async def _handle_web_search(self, args: dict) -> dict:
        """Adapted from Hermes tools/web_tools.py:web_search."""
        from motis_agent.tools.web import motis_web_search
        query = args.get("query", "")
        return await motis_web_search(query=query, ctx=self.ctx)

    async def _handle_web_fetch(self, args: dict) -> dict:
        """Adapted from Hermes tools/web_tools.py:web_extract."""
        from motis_agent.tools.web import motis_web_fetch
        url = args.get("url", "")
        return await motis_web_fetch(url=url, ctx=self.ctx)

    # ── Terminal handler ──────────────────────────────────────────────────────

    async def _handle_terminal(self, args: dict) -> dict:
        """
        Sandboxed Python execution.
        Adapted from Hermes tools/terminal_tool.py.
        Hardened for multi-user: per-user Docker container, 30s timeout, no network.
        TODO Phase 1: implement Docker sandbox. Phase 0: restricted subprocess.
        """
        from motis_agent.tools.terminal import motis_terminal
        command = args.get("command", "")
        return await motis_terminal(command=command, ctx=self.ctx)

    # ── Sub-agent delegation ──────────────────────────────────────────────────

    async def _handle_delegate(self, args: dict) -> dict:
        """
        Adapted from Hermes tools/delegate_tool.py.
        Spawns N concurrent MotisAgentLoop instances with shared UserContext.
        Sub-agents inherit the user's tools but cannot spawn further sub-agents
        (depth limit enforced via sub_depth).
        """
        from motis_agent.tools.subagent import motis_delegate_task
        if self.sub_depth >= MotisToolRouter._MAX_DELEGATE_DEPTH:
            return {"error": "Delegation depth limit reached. Sub-agents cannot spawn further sub-agents."}
        return await motis_delegate_task(args=args, ctx=self.ctx, sub_depth=self.sub_depth + 1)

    _MAX_DELEGATE_DEPTH = 2

    # ── Mixture-of-Agents ─────────────────────────────────────────────────────

    async def _handle_moa(self, args: dict) -> dict:
        """Adapted from Hermes tools/mixture_of_agents_tool.py."""
        from motis_agent.tools.moa import motis_mixture_of_agents
        prompt = args.get("user_prompt", "")
        return await motis_mixture_of_agents(prompt=prompt, ctx=self.ctx)

    # ── Finance skills ────────────────────────────────────────────────────────

    async def _handle_finance_skill(self, tool_name: str, args: dict) -> Any:
        from motis_agent.skills.finance import run_finance_skill
        return await run_finance_skill(tool_name=tool_name, args=args, ctx=self.ctx)
