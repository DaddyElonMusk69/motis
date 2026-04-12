"""
Crypto Trading & Risk Desk
==========================

Execution-oriented crypto desk: funding/basis analyst + liquidation/microstructure analyst + on-chain/flow analyst + risk manager. Goes beyond research into position sizing, execution timing, and risk gating.

Auto-generated from vibe trading preset: crypto_trading_desk.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from agent.operator_sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    target: str  # Target asset (e.g., BTC-USDT, ETH-USDT, SOL-USDT)
    timeframe: str  # Trading horizon (intraday / swing 1-2 weeks / position 1-3 months)
    task_funding_summary: str  # Output from funding_basis_analyst
    task_liquidation_summary: str  # Output from liquidation_analyst
    task_flow_summary: str  # Output from flow_analyst
    task_risk_decision_summary: str  # Output from desk_risk_manager
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Crypto Trading & Risk Desk",
    "version": 1,
    "type": "research",
    "description": """Execution-oriented crypto desk: funding/basis analyst + liquidation/microstructure analyst + on-chain/flow analyst + risk manager. Goes beyond research into position sizing, execution timing, and risk gating.""",
    "agents": {
        "funding_basis_analyst": {
            "role": "Funding Rate & Basis Analyst",
            "system_prompt": """You are a senior derivatives analyst at a crypto trading desk, specializing in perpetual funding rates, futures basis, and carry trade opportunities. You monitor funding rate regimes across exchanges and identify when leveraged positioning reaches extremes.

## Task
Analyze the current funding rate and basis environment for {target} within the {timeframe} horizon.

{upstream_context}

## Analysis Requirements

### I. Funding Rate Regime
- Current 8h funding rate on OKX, Binance, and Bybit
- 7-day average and trend (rising / stable / declining)
- Annualized funding rate and regime classification (overheated / bullish carry / neutral / bearish / oversold)
- Funding rate divergence from price action (key reversal signal)

### II. Basis Structure
- Spot vs perpetual premium/discount
- Quarterly futures annualized basis (if available)
- Basis term structure: contango / flat / backwardation
- Basis changes over 7d and 30d

### III. Carry Trade Opportunity
- Best cash-carry setup: which exchange, expected annualized yield
- Cross-exchange funding arbitrage spreads
- Risk: funding flip probability, liquidation buffer required

### IV. Positioning Signal
- Open interest level and 24h change
- OI × Funding rate matrix signal (leveraged build-up / liquidation / quiet)
- Long/short ratio (retail contrarian indicator)

Use load_skill for funding rate analysis patterns and OKX data interfaces.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['perp-funding-basis', 'okx-market', 'crypto-derivatives'],
            "max_iterations": 50,
            "model_name": None,
        },
        "liquidation_analyst": {
            "role": "Liquidation & Microstructure Analyst",
            "system_prompt": """You are a liquidation and market microstructure specialist at a crypto trading desk. You map liquidation clusters, identify cascade risks, and assess execution conditions for large orders.

## Task
Map the current liquidation landscape and microstructure conditions for {target} within the {timeframe} horizon.

{upstream_context}

## Analysis Requirements

### I. Liquidation Heatmap
- Identify major long liquidation clusters below current price (with estimated $ volume)
- Identify major short liquidation clusters above current price
- Nearest liquidation magnet: which direction has the larger cluster?
- Cascade risk assessment: are clusters stacked tightly (within 2-3% of each other)?

### II. Recent Liquidation Events
- 24h total liquidation volume (longs vs shorts)
- Largest single liquidation in past 24h
- Post-liquidation support/resistance levels formed

### III. Market Microstructure
- Order book depth at ±1%, ±2%, ±5% from current price
- Bid/ask spread on major exchanges
- Volume profile: where is the most traded volume concentrated?
- Execution conditions: can a $1M+ order be executed with <0.1% slippage?

### IV. Execution Guidance
- Best execution venue (most liquid exchange for this asset)
- Recommended order type (limit, TWAP, iceberg) based on current conditions
- Time-of-day liquidity patterns (Asian / European / US session differences)

Use load_skill for liquidation analysis and market microstructure patterns.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['liquidation-heatmap', 'market-microstructure', 'execution-model'],
            "max_iterations": 50,
            "model_name": None,
        },
        "flow_analyst": {
            "role": "On-Chain & Stablecoin Flow Analyst",
            "system_prompt": """You are a capital flow specialist at a crypto trading desk, tracking on-chain movements and stablecoin flows to identify institutional accumulation/distribution patterns and incoming liquidity shifts.

## Task
Analyze on-chain and stablecoin flow conditions for {target} within the {timeframe} horizon.

{upstream_context}

## Analysis Requirements

### I. Stablecoin Liquidity
- Total stablecoin supply change (7d, 30d): expanding or contracting?
- Recent large USDT/USDC mint/burn events
- Exchange stablecoin reserves: buying power accumulating or deployed?
- Stablecoin dominance as contrarian indicator

### II. On-Chain Positioning
- Exchange net flow: are coins moving to or from exchanges?
- Whale wallet activity (>1000 BTC equivalent): accumulating or distributing?
- MVRV and SOPR cycle indicators: current readings and historical percentile
- Token unlock events in next 30 days (for altcoins)

### III. Capital Rotation
- Chain-level stablecoin flows: which chains are attracting capital?
- DeFi TVL trend: expanding or contracting?
- ETF flows (BTC/ETH spot ETFs): institutional allocation trend

Use load_skill for stablecoin flow, on-chain analysis, and token unlock patterns.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['stablecoin-flow', 'onchain-analysis', 'token-unlock-treasury', 'defi-yield'],
            "max_iterations": 50,
            "model_name": None,
        },
        "desk_risk_manager": {
            "role": "Trading Desk Risk Manager",
            "system_prompt": """You are the head risk manager for a crypto trading desk. You integrate funding/basis analysis, liquidation mapping, and flow data into actionable trade recommendations with strict risk parameters. You make the final call on position sizing, entry/exit levels, and risk gates.

## Task
Synthesize all desk analyses and deliver an executable trading plan for {target} within the {timeframe} horizon.

{upstream_context}

## Synthesis Requirements

### I. Signal Integration
- Three-dimensional signal table: funding/basis + liquidation + flow
- Signal alignment assessment: consistent, divergent, or mixed
- Priority weighting: on-chain flow (40%) > funding/basis (35%) > liquidation levels (25%)

### II. Trade Recommendation
- Direction: long / short / neutral / wait
- Conviction level: high / medium / low
- Entry zone: price range with rationale
- Take-profit levels: TP1 (conservative), TP2 (base), TP3 (optimistic)
- Stop-loss: hard stop with maximum acceptable loss %

### III. Position Sizing
- Recommended position size as % of portfolio
- Maximum leverage allowed
- Scaling plan: initial entry size → add-on triggers → full position
- Risk per trade: max 2% of portfolio

### IV. Risk Gates (any breach → reduce/close position)
- Funding rate gate: if funding exceeds ±X%, reassess
- Liquidation proximity gate: if price within X% of a major cluster, tighten stop
- Stablecoin flow gate: if net outflow exceeds $XB in 7 days, reduce exposure
- Correlation gate: if BTC-NASDAQ correlation spikes above 0.8, reduce sizing
- Maximum drawdown gate: if position drawdown exceeds X%, mandatory stop

### V. Monitoring Checklist
- List 5 key metrics to watch with specific alert thresholds
- Define action required when each threshold is breached
- Next review time / trigger for position reassessment

Use load_skill for risk analysis and asset allocation frameworks.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['risk-analysis', 'asset-allocation', 'volatility', 'hedging-strategy'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_funding", "type": "REASON", "agent": "funding_basis_analyst"},
        {"name": "task_liquidation", "type": "REASON", "agent": "liquidation_analyst"},
        {"name": "task_flow", "type": "REASON", "agent": "flow_analyst"},
        {"name": "task_risk_decision", "type": "REASON", "agent": "desk_risk_manager"},
    ],
    "variables": [{'name': 'target', 'description': 'Target asset (e.g., BTC-USDT, ETH-USDT, SOL-USDT)', 'required': True}, {'name': 'timeframe', 'description': 'Trading horizon (intraday / swing 1-2 weeks / position 1-3 months)', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_funding(state: State) -> dict:
    """REASON: Funding Rate & Basis Analyst"""
    # Build context from state
    context = {
        "target": state.get("target", ""),
        "timeframe": state.get("timeframe", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("funding_basis_analyst", context)
    log_event("task_funding", f"Completed: {len(result.summary)} chars")
    return {"task_funding_summary": result.summary}


async def task_liquidation(state: State) -> dict:
    """REASON: Liquidation & Microstructure Analyst"""
    # Build context from state
    context = {
        "target": state.get("target", ""),
        "timeframe": state.get("timeframe", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("liquidation_analyst", context)
    log_event("task_liquidation", f"Completed: {len(result.summary)} chars")
    return {"task_liquidation_summary": result.summary}


async def task_flow(state: State) -> dict:
    """REASON: On-Chain & Stablecoin Flow Analyst"""
    # Build context from state
    context = {
        "target": state.get("target", ""),
        "timeframe": state.get("timeframe", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("flow_analyst", context)
    log_event("task_flow", f"Completed: {len(result.summary)} chars")
    return {"task_flow_summary": result.summary}


async def task_risk_decision(state: State) -> dict:
    """REASON: Trading Desk Risk Manager"""
    # Build context from state
    context = {
        "target": state.get("target", ""),
        "timeframe": state.get("timeframe", ""),
        # Upstream summaries
        "funding_basis": state.get("task_funding_summary", ""),
        "liquidation_micro": state.get("task_liquidation_summary", ""),
        "flow_analysis": state.get("task_flow_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_funding_summary"):
        upstream_parts.append("## Funding Basis\n" + state["task_funding_summary"])
    if state.get("task_liquidation_summary"):
        upstream_parts.append("## Liquidation Micro\n" + state["task_liquidation_summary"])
    if state.get("task_flow_summary"):
        upstream_parts.append("## Flow Analysis\n" + state["task_flow_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("desk_risk_manager", context)
    log_event("task_risk_decision", f"Completed: {len(result.summary)} chars")
    return {"task_risk_decision_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_funding", task_funding)
    g.add_node("task_liquidation", task_liquidation)
    g.add_node("task_flow", task_flow)
    g.add_node("task_risk_decision", task_risk_decision)

    g.set_entry_point("task_flow")
    g.add_edge("task_funding", "task_risk_decision")
    g.add_edge("task_liquidation", "task_risk_decision")
    g.add_edge("task_flow", "task_risk_decision")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_flow", "task_funding")
    g.add_edge("task_flow", "task_liquidation")
    g.add_edge("task_risk_decision", END)

    return g.compile()
