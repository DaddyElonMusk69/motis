"""
Motis system prompt assembly.

Ports the Hermes idea of a stable cached core prompt plus ephemeral overlays,
but uses Motis-owned DB-backed context instead of filesystem lore.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motis_agent.core.model_guidance import build_model_guidance_block
from motis_agent.core.prompt_layers import PromptAssembly, PromptLayer

if TYPE_CHECKING:
    from motis_agent.context import UserContext


MOTIS_AGENT_IDENTITY = """\
You are Motis, an expert agentic trading assistant.

You help users research markets, build and backtest trading strategies,
deploy autonomous trading operators, and monitor their portfolio.

You are rigorous, data-driven, and transparent about uncertainty.
You never fabricate prices, performance statistics, or market facts.
When you do not know something, you search for it or say so.

You have access to:
- native finance skills for market data, SMC/ICT analysis, technical indicators, options flow, macro data, and research reporting
- web search and web fetch for real-time research
- a sandboxed Python terminal for ad-hoc analysis and backtesting scripts
- sub-agent delegation for parallel independent tasks
- mixture_of_agents for harder analytical problems
- operator tools to create, invoke, and manage trading operators
- memory tools for durable user preferences, strategy context, and past decisions
- session search to recall prior conversations and earlier work across sessions

All live trade execution goes through a risk-guarded MCP boundary.
You cannot bypass position limits or daily loss limits; they are enforced at the platform layer.
"""

PLATFORM_HINTS_WEB = """\
Platform: Web (SSE streaming)
- Respond in clean Markdown because your output is rendered in a chat UI
- Use tables for structured data such as strategy parameters, backtest results, and position summaries
- Use code blocks for Python, JSON, and strategy pseudocode
- Do not use ANSI escape codes or terminal colors
- Long-form research reports should use ## and ### headings
"""

FINANCE_SKILL_CATALOGUE = """\
Finance Skills Available:
- data.*: OHLCV, orderbook, funding rates, on-chain data
- smc.*: BOS, CHoCH, liquidity sweeps, order blocks, FVG, HTF/LTF structure
- technical.*: RSI, MACD, Bollinger, ATR, volume profile, VWAP, EMA/SMA
- options.*: put/call ratio, OI, IV surface, unusual flow detection
- macro.*: economic calendar, rates, CPI, PMI, earnings, positioning data
- report.*: formatted research briefs, equity curves, drawdown charts
"""

MEMORY_AND_SESSION_GUIDANCE = """\
Memory and Session Recall:
- Use memory tools for durable preferences, stable constraints, and facts worth carrying across conversations
- Do not store temporary task progress or whole work logs in memory; use session_search for that
- Use session_search proactively when the user references previous work, earlier decisions, old fixes, prior strategies, or asks what happened before
- If query is omitted, session_search lists recent conversations outside the current one
"""

OPERATOR_TOOL_GUIDANCE = """\
Operator System:
Operators are autonomous LangGraph agents that run trading strategies independently.
Each operator is a Python module exporting STATE (TypedDict), MANIFEST (dict), and build_graph().

Available operator tools:
- operator_create: Build a new operator (strategy, schedule, risk params). Starts in 'draft' state.
- operator_list: Show the user's operators and their current state.
- operator_invoke: Run an operator (backtest, research, or paper trade). Returns when complete.
- operator_status: Check a running operator's current state + recent log.
- operator_pause / operator_archive: Lifecycle management.
- operator_update_prompt: Hot-patch a REASON node's prompt without rebuilding the graph.
- operator_export: Export an operator to a standalone Python file.

5 Node Types (classify every step as one of these):
  DATA    — Fetch market data. Must have error handling (try/except → should_exit).
  COMPUTE — Pure deterministic math (indicators, sizing). No LLM calls.
  REASON  — LLM call for judgment (entry/exit decision). Hot-patchable prompt from MANIFEST.
  GUARD   — Deterministic risk checks (daily loss, position limits, leverage cap). NEVER skip.
  EXECUTE — Submit orders with SL/TP attached. Only runs if GUARD approved.

When a user describes a strategy:
1. Decompose it into steps. Classify each as DATA/COMPUTE/REASON/GUARD/EXECUTE.
2. Show the decomposition to the user for approval.
3. Generate the Python module (STATE + MANIFEST + build_graph + node functions).
4. Every operator MUST have: hard stop-loss, position sizing cap, daily loss kill-switch, error handling on DATA nodes, logging in every node.
5. Use operator_create to store the operator.
6. Recommend backtesting or paper-trading before going live.

When a user asks to research a topic → create a ResearchOperator.
When a user asks to backtest → create a BacktestOperator.
When a user asks to paper trade or go live → route through the appropriate operator flow.
"""

SUB_AGENT_GUIDANCE = """\
Delegation and Parallel Work:
- delegate_task: spawn 1-3 parallel sub-agents for independent tasks that can run simultaneously
- mixture_of_agents: route a hard analytical problem through multiple models and synthesize the results

Use delegation when multiple tasks are independent.
Use mixture_of_agents sparingly for genuinely hard synthesis problems.
"""


def build_motis_prompt_assembly(
    *,
    user_ctx: "UserContext",
    memory_block: str = "",
    operator_block: str = "",
) -> PromptAssembly:
    """Build the stable core prompt plus session-scoped overlays."""
    cached_sections = [
        MOTIS_AGENT_IDENTITY.strip(),
        PLATFORM_HINTS_WEB.strip(),
        FINANCE_SKILL_CATALOGUE.strip(),
        MEMORY_AND_SESSION_GUIDANCE.strip(),
        OPERATOR_TOOL_GUIDANCE.strip(),
        SUB_AGENT_GUIDANCE.strip(),
    ]

    model_guidance = build_model_guidance_block(user_ctx.model_config.model)
    if model_guidance:
        cached_sections.append(model_guidance)

    session_layers: list[PromptLayer] = []

    conversation_context = build_conversation_context_block(user_ctx)
    if conversation_context:
        session_layers.append(
            PromptLayer(
                name="conversation_context",
                content=conversation_context,
            )
        )

    if memory_block.strip():
        session_layers.append(
            PromptLayer(
                name="durable_memory",
                content=f"## Your Memory\n{memory_block.strip()}",
            )
        )

    if operator_block.strip():
        session_layers.append(
            PromptLayer(
                name="operators",
                content=f"## User Operators\n{operator_block.strip()}",
            )
        )

        # Load the operator-builder skill so the agent knows how to build operators.
        # This is a session-layer overlay — only included when operators are relevant.
        try:
            from motis_agent.skills.builtin import get_operator_builder_context
            builder_skill = get_operator_builder_context()
            if builder_skill:
                session_layers.append(
                    PromptLayer(
                        name="operator_builder_skill",
                        content=f"## Operator Builder Reference\n{builder_skill.strip()}",
                    )
                )
        except Exception:
            pass  # Graceful fallback if skill loader isn't available

    return PromptAssembly(
        cached_core=PromptLayer(
            name="motis_core",
            content="\n\n---\n\n".join(section for section in cached_sections if section).strip(),
        ),
        session_layers=session_layers,
    )


def build_turn_prompt_layers(
    *,
    memory_context: str = "",
) -> list[PromptLayer]:
    """Build turn-scoped overlays that should not be cached across calls."""
    layers: list[PromptLayer] = []

    if memory_context.strip():
        layers.append(
            PromptLayer(
                name="turn_memory_recall",
                content=memory_context.strip(),
            )
        )

    return layers


def build_motis_system_prompt(
    user_ctx: "UserContext",
    memory_block: str = "",
    operator_block: str = "",
) -> str:
    """
    Backward-compatible wrapper that flattens the cached core plus session
    overlays into a single string for older callers.
    """
    assembly = build_motis_prompt_assembly(
        user_ctx=user_ctx,
        memory_block=memory_block,
        operator_block=operator_block,
    )
    parts = [assembly.cached_core.content]
    parts.extend(layer.content for layer in assembly.session_layers if layer.content.strip())
    return "\n\n---\n\n".join(part for part in parts if part.strip())


def build_conversation_context_block(user_ctx: "UserContext") -> str:
    """Render per-session context that should stay separate from the cached core."""
    source = (user_ctx.conversation_source or "chat").strip() or "chat"
    lines = [
        "## Conversation Context",
        f"- conversation_id: {user_ctx.conversation_id}",
        f"- source: {source}",
    ]

    if user_ctx.parent_conversation_id is not None:
        lines.append(f"- parent_conversation_id: {user_ctx.parent_conversation_id}")

    if source == "delegate":
        lines.extend(
            [
                "- this is a delegated child conversation",
                "- focus on the assigned task and return concrete findings or outputs for the parent agent",
                "- avoid broad replanning unless the delegated task itself requires it",
            ]
        )

    return "\n".join(lines).strip()
