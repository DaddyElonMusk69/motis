"""
Motis Tool Router
=================
Dispatches tool calls from MotisAgentLoop to the appropriate handler.

Two dispatch paths:
1. Native tools (finance skills, memory, web, terminal, subagent, moa)
   → imported and called directly in-process
2. Remote execution tools (execute_*, get_positions)
   → forwarded via HTTP to the Motis MCP server

Adapted from Hermes model_tools.py:handle_function_call()
Key difference: no process-global tool registry — tools are resolved
per-request from UserContext.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from motis_agent.context import UserContext

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from motis_agent.core.budget import IterationBudget


# Tools dispatched via MCP HTTP (services/mcp)
_MCP_TOOLS = frozenset({
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

    def __init__(
        self,
        ctx: UserContext,
        *,
        sub_depth: int = 0,
        iteration_budget: "IterationBudget | None" = None,
        progress_callback: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ):
        self.ctx = ctx
        self.sub_depth = sub_depth
        self.iteration_budget = iteration_budget
        self.progress_callback = progress_callback

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
        Injects user context headers so the remote execution layer can enforce
        risk guards and inject the correct exchange API keys.
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
        if tool_name == "session_search":
            return await self._handle_session_search(args)

        # Operator tools live in Motis locally, not in the remote MCP boundary.
        if tool_name == "operator_create":
            return await self._handle_operator_create(args)
        if tool_name == "operator_list":
            return await self._handle_operator_list(args)
        if tool_name == "operator_invoke":
            return await self._handle_operator_invoke(args)
        if tool_name == "operator_status":
            return await self._handle_operator_status(args)
        if tool_name == "operator_pause":
            return await self._handle_operator_pause(args)
        if tool_name == "operator_archive":
            return await self._handle_operator_archive(args)
        if tool_name == "operator_update_prompt":
            return await self._handle_operator_update_prompt(args)
        if tool_name == "operator_export":
            return await self._handle_operator_export(args)

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
        return await self.ctx.memory_manager.handle_tool_call("memory_add", args)

    async def _handle_memory_search(self, args: dict) -> dict:
        return await self.ctx.memory_manager.handle_tool_call("memory_search", args)

    async def _handle_memory_recall(self, args: dict) -> dict:
        return await self.ctx.memory_manager.handle_tool_call("memory_recall", args)

    async def _handle_session_search(self, args: dict) -> dict:
        return await self.ctx.session_search.search(
            query=args.get("query", ""),
            role_filter=args.get("role_filter"),
            limit=args.get("limit", 3),
            include_child_sessions=args.get("include_child_sessions", False),
        )

    # ── Operator handlers ────────────────────────────────────────────────────

    async def _handle_operator_create(self, args: dict) -> dict:
        return await self.ctx.operator_service.create(
            name=args.get("name", "Untitled Operator"),
            operator_type=args.get("type", "live_trade"),
            spec=args.get("spec") or {},
        )

    async def _handle_operator_list(self, args: dict) -> dict:
        return await self.ctx.operator_service.list(
            state_filter=args.get("state_filter", "all"),
        )

    async def _handle_operator_invoke(self, args: dict) -> dict:
        from uuid import UUID

        operator_id = UUID(args.get("operator_id", ""))
        return await self.ctx.operator_service.invoke(
            operator_id=operator_id,
            input_payload=args.get("input"),
        )

    async def _handle_operator_status(self, args: dict) -> dict:
        from uuid import UUID

        operator_id = UUID(args.get("operator_id", ""))
        return await self.ctx.operator_service.status(operator_id=operator_id)

    async def _handle_operator_pause(self, args: dict) -> dict:
        from uuid import UUID

        operator_id = UUID(args.get("operator_id", ""))
        return await self.ctx.operator_service.pause(
            operator_id=operator_id,
            reason=args.get("reason", ""),
        )

    async def _handle_operator_archive(self, args: dict) -> dict:
        from uuid import UUID

        operator_id = UUID(args.get("operator_id", ""))
        return await self.ctx.operator_service.archive(operator_id=operator_id)

    async def _handle_operator_update_prompt(self, args: dict) -> dict:
        """
        Hot-patch a REASON node's prompt within a loaded operator.
        Design reference: docs/operators/03-sdk-and-execution.md §Hot-Patching
        """
        operator_id = args.get("operator_id", "")
        node_name = args.get("node_name", "")
        prompt = args.get("prompt", "")

        loaded = await self.ctx.operator_registry.get_loaded_operator(operator_id)
        if loaded is None:
            return {"ok": False, "error": f"Operator {operator_id} not found or not loaded"}

        manifest = loaded.manifest
        reason_prompts = manifest.get("reason_prompts", {})
        old_prompt = reason_prompts.get(node_name)
        if old_prompt is None:
            return {
                "ok": False,
                "error": f"Node '{node_name}' has no reason_prompt entry in MANIFEST",
                "available_nodes": list(reason_prompts.keys()),
            }

        reason_prompts[node_name] = prompt
        return {
            "ok": True,
            "operator_id": operator_id,
            "node_name": node_name,
            "message": f"Prompt for '{node_name}' updated successfully",
        }

    async def _handle_operator_export(self, args: dict) -> dict:
        """
        Export an operator's Python source to a file.
        Design reference: docs/operators/01-architecture-overview.md §Export/Import Flow
        """
        operator_id = args.get("operator_id", "")
        loaded = await self.ctx.operator_registry.get_loaded_operator(operator_id)

        if loaded is None:
            return {"ok": False, "error": f"Operator {operator_id} not found or not loaded"}

        # For filesystem operators, return the source file path
        module = loaded.module
        if hasattr(module, "__file__") and module.__file__:
            return {
                "ok": True,
                "operator_id": operator_id,
                "source_path": module.__file__,
                "message": f"Operator source at: {module.__file__}",
            }

        return {
            "ok": False,
            "operator_id": operator_id,
            "message": "Operator source export from DB not yet implemented.",
        }

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
        return await motis_delegate_task(
            args=args,
            ctx=self.ctx,
            sub_depth=self.sub_depth + 1,
            iteration_budget=self.iteration_budget,
            progress_callback=self.progress_callback,
        )

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
