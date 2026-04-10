"""
Quant Strategy Desk
===================

Stock screening + factor research in parallel → strategy backtest → risk audit.

Auto-generated from vibe trading preset: quant_strategy_desk.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    market: str  # Target market
    goal: str  # Strategy objective (e.g., momentum + value dual factor)
    task_screen_summary: str  # Output from screener
    task_factor_summary: str  # Output from factor_miner
    task_backtest_summary: str  # Output from backtester
    task_risk_summary: str  # Output from risk_auditor
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Quant Strategy Desk",
    "version": 1,
    "type": "research",
    "description": """Stock screening + factor research in parallel → strategy backtest → risk audit.""",
    "agents": {
        "screener": {
            "role": "Stock Screener",
            "system_prompt": """You are a quant stock-screening specialist, skilled in multi-criteria screening and fundamental pre-filtering.

## Task
For the strategy objective, screen a candidate universe from {market}.

{upstream_context}

## Required outputs
1. **Screening criteria** — List every screening dimension and threshold explicitly
2. **Candidate list** — At least 10–20 candidates (code + name + sector)
3. **Fundamental snapshot** — Core metrics per name (PE/PB/ROE/market cap, etc.)
4. **Screening funnel stats** — Initial universe size → remaining count after each filtering step

Use factor_analysis for factor-based screening.
Use load_skill for data access patterns.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['tushare', 'fundamental-filter'],
            "max_iterations": 50,
            "model_name": None,
        },
        "factor_miner": {
            "role": "Factor Researcher",
            "system_prompt": """You are a quant factor researcher, skilled in alpha factor mining, factor testing, and factor combination.

## Task
For the strategy objective in {market}, mine effective alpha factors.

{upstream_context}

## Required outputs
1. **Candidate factor list** — At least 5 factors (name, formula, economic rationale)
2. **Factor tests** — Mean IC, ICIR, IC hit rate, factor return
3. **Factor correlation** — Correlation matrix; remove highly correlated factors
4. **Factor combination** — Suggest equal-weight or optimized combo of 3–5 factors
5. **Risk notes** — Factor-decay scenarios and cyclicality

Use factor_analysis for computations.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['multi-factor', 'factor-research'],
            "max_iterations": 50,
            "model_name": None,
        },
        "backtester": {
            "role": "Strategy Backtester",
            "system_prompt": """You are a strategy backtest specialist, skilled in turning screening + factor work into backtestable quant strategies.

## Task
Build the strategy from screening and factor research and run a backtest.

{upstream_context}

## Required outputs
1. **Strategy logic** — Complete buy/sell rules in prose
2. **Strategy code** — Follow load_skill("strategy-generate") standards
3. **Backtest metrics** — Annualized return, Sharpe, max drawdown, win rate, profit/loss ratio
4. **Equity curve commentary** — Phase-by-phase performance vs benchmark excess
5. **Improvement ideas** — Potential optimizations

You must run **backtest** with real outputs—do not fabricate numbers.""",
            "tools": ['bash', 'read_file', 'write_file', 'edit_file', 'load_skill', 'backtest'],
            "skills": ['strategy-generate', 'technical-basic'],
            "max_iterations": 50,
            "model_name": None,
        },
        "risk_auditor": {
            "role": "Risk Auditor",
            "system_prompt": """You are a quant risk auditor, skilled in reviewing strategy quality from a risk perspective.

## Task
Audit risk exposures in the backtest and assess robustness.

{upstream_context}

## Required outputs
1. **Drawdown analysis** — Top historical drawdowns: drivers and duration
2. **Volatility assessment** — Annual vol, downside vol, volatility clustering
3. **Tail risk** — VaR/CVaR estimates; behavior in extreme markets
4. **Overfitting checks** — In-sample vs out-of-sample gaps; parameter sensitivity
5. **Risk recommendations** — Position sizing, stops, risk-control improvements

Use load_skill for volatility methods.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['volatility'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_screen", "type": "REASON", "agent": "screener"},
        {"name": "task_factor", "type": "REASON", "agent": "factor_miner"},
        {"name": "task_backtest", "type": "REASON", "agent": "backtester"},
        {"name": "task_risk", "type": "REASON", "agent": "risk_auditor"},
    ],
    "variables": [{'name': 'market', 'description': 'Target market', 'required': True}, {'name': 'goal', 'description': 'Strategy objective (e.g., momentum + value dual factor)', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_screen(state: State) -> dict:
    """REASON: Stock Screener"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("screener", context)
    log_event("task_screen", f"Completed: {len(result.summary)} chars")
    return {"task_screen_summary": result.summary}


async def task_factor(state: State) -> dict:
    """REASON: Factor Researcher"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("factor_miner", context)
    log_event("task_factor", f"Completed: {len(result.summary)} chars")
    return {"task_factor_summary": result.summary}


async def task_backtest(state: State) -> dict:
    """REASON: Strategy Backtester"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        # Upstream summaries
        "screener_result": state.get("task_screen_summary", ""),
        "factors": state.get("task_factor_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_screen_summary"):
        upstream_parts.append("## Screener Result\n" + state["task_screen_summary"])
    if state.get("task_factor_summary"):
        upstream_parts.append("## Factors\n" + state["task_factor_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("backtester", context)
    log_event("task_backtest", f"Completed: {len(result.summary)} chars")
    return {"task_backtest_summary": result.summary}


async def task_risk(state: State) -> dict:
    """REASON: Risk Auditor"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        # Upstream summaries
        "backtest_result": state.get("task_backtest_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_backtest_summary"):
        upstream_parts.append("## Backtest Result\n" + state["task_backtest_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("risk_auditor", context)
    log_event("task_risk", f"Completed: {len(result.summary)} chars")
    return {"task_risk_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_screen", task_screen)
    g.add_node("task_factor", task_factor)
    g.add_node("task_backtest", task_backtest)
    g.add_node("task_risk", task_risk)

    g.set_entry_point("task_factor")
    g.add_edge("task_screen", "task_backtest")
    g.add_edge("task_factor", "task_backtest")
    g.add_edge("task_backtest", "task_risk")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_factor", "task_screen")
    g.add_edge("task_risk", END)

    return g.compile()
