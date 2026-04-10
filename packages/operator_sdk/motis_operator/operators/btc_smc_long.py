"""
Example: BTC SMC Long Operator (Stub)
======================================
This is a reference operator that demonstrates the operator contract.
It loads successfully in dev mode and shows up in the master agent's
system prompt as an available operator.

This is a STUB — it defines the correct contract shape but does not
execute real trades. Replace the node implementations with real logic
when the SDK is fully wired.

Contract reference: docs/operators/02-contract-and-validation.md
Node types reference: docs/operators/02-contract-and-validation.md §The 5 Node Types
SDK reference: docs/operators/03-sdk-and-execution.md §The SDK Surface
"""

from __future__ import annotations

from typing import Optional, TypedDict


# ── STATE ──────────────────────────────────────────────────────────────────────
# Every field the graph reads or writes. Grouped by the node type that owns it.

class State(TypedDict):
    # DATA
    ohlcv: list[dict]
    current_positions: list[dict]
    daily_pnl_usd: float

    # COMPUTE
    smc_analysis: dict                  # BOS, CHoCH, sweeps, OBs

    # REASON
    signal: Optional[dict]              # {direction, confidence, entry, sl, tp}

    # COMPUTE (sizing)
    sized_signal: Optional[dict]        # signal + size_usd

    # GUARD
    guard_approved: bool
    guard_reason: str

    # EXECUTE
    orders: list[dict]

    # Control flow
    should_exit: bool
    run_log: list[dict]


STATE = State


# ── MANIFEST ───────────────────────────────────────────────────────────────────

MANIFEST = {
    "name": "BTC SMC Long (Example)",
    "version": 1,
    "type": "paper_trade",
    "asset_class": "crypto_perp",
    "asset_universe": ["BTC/USDT:USDT"],
    "exchange": "hyperliquid",
    "trigger": {"type": "cron", "expression": "*/15 * * * *"},
    "risk": {
        "max_position_size_pct": 10.0,
        "max_daily_loss_pct": 5.0,
        "max_leverage": 3.0,
        "max_open_positions": 3,
        "risk_per_trade_pct": 2.0,
    },
    "reason_prompts": {
        "analyze_entry": (
            "You are a crypto trader specializing in SMC/ICT methodology.\n"
            "Analyze the following market structure and determine if there is "
            "a valid LONG entry.\n\n"
            "Rules:\n"
            "- Only enter after a confirmed bullish BOS\n"
            "- A liquidity sweep must have occurred within the last 10 candles\n"
            "- Entry should be at or near a bullish order block\n"
            "- SL must be below the sweep low\n"
            "- TP should target the next bearish order block or recent high\n\n"
            "Recent structure:\n{smc_summary}\n\n"
            "Current price: {current_price}\n\n"
            'Respond as JSON: {{"direction": "long"|"flat", "confidence": 0.0-1.0, '
            '"reasoning": "...", "entry": price, "sl": price, "tp": price}}'
        ),
    },
    "nodes": [
        {"name": "fetch_data",       "type": "DATA"},
        {"name": "calc_smc",         "type": "COMPUTE"},
        {"name": "analyze_entry",    "type": "REASON"},
        {"name": "size_position",    "type": "COMPUTE"},
        {"name": "risk_guard",       "type": "GUARD"},
        {"name": "execute_orders",   "type": "EXECUTE"},
    ],
}


# ── NODE IMPLEMENTATIONS (stubs) ──────────────────────────────────────────────

async def fetch_data(state: State) -> dict:
    """DATA: Fetch OHLCV + current positions + daily P&L."""
    return {"ohlcv": [], "current_positions": [], "daily_pnl_usd": 0.0}


async def calc_smc(state: State) -> dict:
    """COMPUTE: Run SMC structure detection (deterministic)."""
    return {"smc_analysis": {}}


async def analyze_entry(state: State) -> dict:
    """REASON: LLM decides whether to enter (hot-patchable prompt)."""
    return {"signal": None, "should_exit": True}


async def size_position(state: State) -> dict:
    """COMPUTE: Deterministic position sizing."""
    return {"sized_signal": None, "should_exit": True}


async def risk_guard(state: State) -> dict:
    """GUARD: Baked-in risk checks."""
    return {"guard_approved": False, "guard_reason": "stub — not implemented"}


async def execute_orders(state: State) -> dict:
    """EXECUTE: Submit orders with SL/TP."""
    return {"orders": []}


# ── GRAPH ASSEMBLY ─────────────────────────────────────────────────────────────

def build_graph():
    """
    Build and return the compiled LangGraph StateGraph.

    This stub returns a minimal graph. Replace with a full LangGraph
    implementation when the SDK + LangGraph dependencies are installed.
    """
    # Delayed import — LangGraph may not be installed in all environments.
    # When it's not available, we return a simple callable that runs the
    # nodes sequentially. This lets the operator load and be visible to the
    # agent even before LangGraph is set up.
    try:
        from langgraph.graph import StateGraph, END

        g = StateGraph(State)
        g.add_node("fetch_data", fetch_data)
        g.add_node("calc_smc", calc_smc)
        g.add_node("analyze_entry", analyze_entry)
        g.add_node("size_position", size_position)
        g.add_node("risk_guard", risk_guard)
        g.add_node("execute_orders", execute_orders)

        g.set_entry_point("fetch_data")
        g.add_edge("fetch_data", "calc_smc")
        g.add_edge("calc_smc", "analyze_entry")
        g.add_conditional_edges(
            "analyze_entry",
            lambda s: "exit" if s.get("should_exit") else "continue",
            {"exit": END, "continue": "size_position"},
        )
        g.add_edge("size_position", "risk_guard")
        g.add_conditional_edges(
            "risk_guard",
            lambda s: "execute" if s.get("guard_approved") else "exit",
            {"execute": "execute_orders", "exit": END},
        )
        g.add_edge("execute_orders", END)

        return g.compile()

    except ImportError:
        # Fallback: return a simple async callable that runs nodes in sequence.
        # This is enough for the registry to validate the contract.
        async def _sequential_runner(input_state: dict | None = None) -> dict:
            state = dict(input_state or {})
            for node_fn in [fetch_data, calc_smc, analyze_entry, size_position, risk_guard, execute_orders]:
                if state.get("should_exit"):
                    break
                update = await node_fn(state)
                state.update(update)
            return state
        return _sequential_runner
