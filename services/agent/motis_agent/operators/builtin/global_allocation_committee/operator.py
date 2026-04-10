"""
Global Allocation Committee
===========================

Parallel A-shares + crypto + HK/US analysts; allocator synthesizes cross-market allocation with data-driven weighting, scenario analysis, and rebalancing rules.

Auto-generated from vibe trading preset: global_allocation_committee.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    goal: str  # Investment objective (e.g., Q2 2026 multi-asset allocation)
    risk_tolerance: str  # Risk tolerance (conservative / moderate / aggressive)
    task_ashare_summary: str  # Output from a_share_analyst
    task_crypto_summary: str  # Output from crypto_analyst
    task_ushk_summary: str  # Output from us_hk_analyst
    task_allocate_summary: str  # Output from allocator
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Global Allocation Committee",
    "version": 1,
    "type": "research",
    "description": """Parallel A-shares + crypto + HK/US analysts; allocator synthesizes cross-market allocation with data-driven weighting, scenario analysis, and rebalancing rules.""",
    "agents": {
        "a_share_analyst": {
            "role": "A-Share Analyst",
            "system_prompt": """You are a senior A-share market analyst skilled in market structure, sector rotation, and security screening. You combine top-down macro with bottom-up stock selection.

## Task
Analyze current A-share investment opportunities and risks for: {goal}.

{upstream_context}

## Output Requirements
1. **Market overview** — index trend (CSI 300/500/1000), volume, sentiment proxies (margin balance, new accounts)
2. **Northbound flow signal** — 20-day cumulative foreign capital flow, sector allocation shift
3. **Sector rotation** — which sectors are leading (with data), which are lagging, rotation direction
4. **Top picks** — 3-5 A-share tickers with: code, name, sector, PE, PB, ROE, entry rationale
5. **Return outlook** — price targets or expected return range where reasonable
6. **Risks** — policy risk, liquidity risk, valuation risk specific to A-shares

Use load_skill for Tushare data patterns, Northbound flow analysis, and fundamental screening.
Use factor_analysis tool for quantitative factor scoring where helpful.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['tushare', 'technical-basic', 'fundamental-filter', 'hk-connect-flow', 'sector-rotation', 'multi-factor'],
            "max_iterations": 50,
            "model_name": None,
        },
        "crypto_analyst": {
            "role": "Crypto Analyst",
            "system_prompt": """You are a senior crypto analyst covering trend, volatility, and derivative positioning for major digital assets.

## Task
Analyze major crypto assets for opportunities and risks in the context of: {goal}.

{upstream_context}

## Output Requirements
1. **Market overview** — BTC dominance, total market cap, Fear & Greed index
2. **Funding & basis** — current funding rate regime, annualized basis, carry trade viability
3. **Stablecoin flows** — supply trend, exchange reserves, fresh capital signals
4. **Core assets** — BTC / ETH / SOL trend analysis with key levels
5. **Top picks** — 3-5 tickers in BTC-USDT format with direction and rationale
6. **Volatility** — realized vs implied, positioning extremes, liquidation risk zones

Use load_skill for OKX market data, funding rate analysis, and stablecoin flow patterns.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['okx-market', 'perp-funding-basis', 'stablecoin-flow', 'crypto-derivatives', 'volatility', 'onchain-analysis'],
            "max_iterations": 50,
            "model_name": None,
        },
        "us_hk_analyst": {
            "role": "HK / US Analyst",
            "system_prompt": """You are a senior HK and US equities analyst with a global lens. You use yfinance for market data, track ETF flows for institutional positioning, and analyze cross-listing dynamics.

## Task
Analyze HK and US equity opportunities for: {goal}.

{upstream_context}

## Output Requirements
1. **US market** — S&P 500, NASDAQ, Russell 2000 trend; sector ETF flow signals (cyclical vs defensive)
2. **HK market** — Hang Seng trend; Southbound flow analysis; AH premium level
3. **Earnings pulse** — which major companies reported recently? Surprise direction and revision momentum
4. **Top picks** — 3-5 tickers (AAPL.US, 0700.HK format) with: sector, PE, earnings revision direction, catalyst
5. **Cross-listing** — any ADR/H-share arbitrage opportunities? Delisting risk assessment for Chinese ADRs
6. **FX** — USD/CNY and USD/HKD impact on the portfolio; hedging considerations

Use load_skill for yfinance data, ETF flow analysis, earnings revision patterns, and cross-listing dynamics.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['yfinance', 'us-etf-flow', 'earnings-revision', 'adr-hshare', 'hk-connect-flow', 'technical-basic'],
            "max_iterations": 50,
            "model_name": None,
        },
        "allocator": {
            "role": "Allocation Strategist",
            "system_prompt": """You are a senior cross-market allocator responsible for synthesizing three regional reports into a unified portfolio recommendation. You balance risk and return across markets with data-driven allocation.

## Task
Optimize cross-market allocation using the three regional reports. Risk tolerance: {risk_tolerance}. Goal: {goal}.

{upstream_context}

## Output Requirements
1. **Signal alignment** — compare directional signals across three regions: agreement / divergence / mixed
2. **Allocation weights** — A-share / crypto / HK-US / cash split with explicit rationale for each weight
   - Conservative: 50% A-share, 25% HK/US, 10% crypto, 15% cash
   - Moderate: 40% A-share, 25% HK/US, 20% crypto, 15% cash
   - Aggressive: 30% A-share, 20% HK/US, 35% crypto, 15% cash
   - Adjust from these baselines based on current market signals
3. **Security selection** — final portfolio (max 15 names), with per-name weight
4. **Correlation assessment** — cross-market correlation (A-share vs NASDAQ, BTC vs tech, HK vs A-share)
5. **Risk/return profile** — expected portfolio vol, Sharpe-style framing
6. **Rebalancing rules** — threshold-based triggers (>5% drift from target → rebalance)
7. **Scenario analysis**:
   - Bull case (probability X%): description, allocation shift
   - Base case (probability X%): description, hold allocation
   - Bear case (probability X%): description, defensive shift

You may use backtest to validate historical behavior of the proposed allocation.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest'],
            "skills": ['asset-allocation', 'risk-analysis', 'correlation-analysis', 'strategy-generate'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_ashare", "type": "REASON", "agent": "a_share_analyst"},
        {"name": "task_crypto", "type": "REASON", "agent": "crypto_analyst"},
        {"name": "task_ushk", "type": "REASON", "agent": "us_hk_analyst"},
        {"name": "task_allocate", "type": "REASON", "agent": "allocator"},
    ],
    "variables": [{'name': 'goal', 'description': 'Investment objective (e.g., Q2 2026 multi-asset allocation)', 'required': True}, {'name': 'risk_tolerance', 'description': 'Risk tolerance (conservative / moderate / aggressive)', 'required': False}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_ashare(state: State) -> dict:
    """REASON: A-Share Analyst"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
        "risk_tolerance": state.get("risk_tolerance", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("a_share_analyst", context)
    log_event("task_ashare", f"Completed: {len(result.summary)} chars")
    return {"task_ashare_summary": result.summary}


async def task_crypto(state: State) -> dict:
    """REASON: Crypto Analyst"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
        "risk_tolerance": state.get("risk_tolerance", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("crypto_analyst", context)
    log_event("task_crypto", f"Completed: {len(result.summary)} chars")
    return {"task_crypto_summary": result.summary}


async def task_ushk(state: State) -> dict:
    """REASON: HK / US Analyst"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
        "risk_tolerance": state.get("risk_tolerance", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("us_hk_analyst", context)
    log_event("task_ushk", f"Completed: {len(result.summary)} chars")
    return {"task_ushk_summary": result.summary}


async def task_allocate(state: State) -> dict:
    """REASON: Allocation Strategist"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
        "risk_tolerance": state.get("risk_tolerance", ""),
        # Upstream summaries
        "a_share": state.get("task_ashare_summary", ""),
        "crypto": state.get("task_crypto_summary", ""),
        "us_hk": state.get("task_ushk_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_ashare_summary"):
        upstream_parts.append("## A Share\n" + state["task_ashare_summary"])
    if state.get("task_crypto_summary"):
        upstream_parts.append("## Crypto\n" + state["task_crypto_summary"])
    if state.get("task_ushk_summary"):
        upstream_parts.append("## Us Hk\n" + state["task_ushk_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("allocator", context)
    log_event("task_allocate", f"Completed: {len(result.summary)} chars")
    return {"task_allocate_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_ashare", task_ashare)
    g.add_node("task_crypto", task_crypto)
    g.add_node("task_ushk", task_ushk)
    g.add_node("task_allocate", task_allocate)

    g.set_entry_point("task_ashare")
    g.add_edge("task_ashare", "task_allocate")
    g.add_edge("task_crypto", "task_allocate")
    g.add_edge("task_ushk", "task_allocate")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_ashare", "task_crypto")
    g.add_edge("task_ashare", "task_ushk")
    g.add_edge("task_allocate", END)

    return g.compile()
