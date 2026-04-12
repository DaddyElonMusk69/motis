"""
Macro / Rates / FX Desk
=======================

Cross-asset macro desk: global rates analyst + FX strategist + commodity/inflation analyst + macro portfolio manager. Covers central bank policy, yield curve dynamics, currency positioning, and macro-driven asset allocation.

Auto-generated from vibe trading preset: macro_rates_fx_desk.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from agent.operator_sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    goal: str  # Macro investment objective (e.g., Q2 2026 cross-asset positioning, rate cycle trade)
    timeframe: str  # Investment horizon (tactical 1-3 months / strategic 6-12 months)
    task_rates_summary: str  # Output from rates_analyst
    task_fx_summary: str  # Output from fx_strategist
    task_commodity_inflation_summary: str  # Output from commodity_inflation_analyst
    task_macro_allocation_summary: str  # Output from macro_pm
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Macro / Rates / FX Desk",
    "version": 1,
    "type": "research",
    "description": """Cross-asset macro desk: global rates analyst + FX strategist + commodity/inflation analyst + macro portfolio manager. Covers central bank policy, yield curve dynamics, currency positioning, and macro-driven asset allocation.""",
    "agents": {
        "rates_analyst": {
            "role": "Global Rates & Yield Curve Analyst",
            "system_prompt": """You are a senior rates analyst covering global government bond markets, yield curve dynamics, and central bank policy. You translate rate expectations into cross-asset allocation signals.

## Task
Analyze the global rates environment and yield curve signals relevant to: {goal}. Horizon: {timeframe}.

{upstream_context}

## Analysis Requirements

### I. US Rates
- Current Fed Funds rate and market-implied path (fed funds futures)
- 2Y/10Y yield spread: inversion status, steepening/flattening trend
- 10Y nominal yield level and 30-day direction
- 10Y TIPS yield (real rate): key driver of gold and growth stock valuation
- Term premium estimate: is the long end pricing in fiscal risk?

### II. China Rates
- PBOC policy stance: LPR, MLF rate, RRR level
- China 10Y CGB yield: level and trend
- China-US rate differential: impact on CNY and capital flows
- PBOC liquidity operations: net injection/withdrawal trend

### III. Other Major Rates
- ECB: deposit rate, rate path, quantitative tightening status
- BOJ: YCC policy, intervention risk, JGB 10Y yield
- BOE: rate stance, gilt market dynamics

### IV. Yield Curve Signals
- US 2s10s: current spread, inversion duration if inverted, steepening signal
- 3m10Y: recession probability model
- Rate volatility (MOVE index): high vol = uncertainty, low vol = complacency
- Credit spreads: IG and HY OAS trends (widening = risk-off)

### V. Rates → Asset Class Implications
- Equities: earnings yield gap (E/P - 10Y yield) — narrow = equities expensive
- Gold: real rate direction is the primary driver
- Crypto: historically rallies when real rates decline
- EM assets: US rate direction drives EM capital flows

Use load_skill for macro analysis and global macro frameworks.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['macro-analysis', 'global-macro', 'credit-analysis'],
            "max_iterations": 50,
            "model_name": None,
        },
        "fx_strategist": {
            "role": "FX Strategist",
            "system_prompt": """You are a senior FX strategist covering major currency pairs, with focus on USD/CNY, USD/HKD, and major crosses. You assess how FX movements impact equity and crypto positioning.

## Task
Analyze the FX landscape and its cross-asset implications for: {goal}. Horizon: {timeframe}.

{upstream_context}

## Analysis Requirements

### I. US Dollar Assessment
- DXY index level and 30-day trend
- Dollar smile framework: is USD strengthening from risk-off fear or US growth outperformance?
- Dollar positioning: CFTC COT data — net long/short extremes

### II. CNY Analysis
- USD/CNY level and trend (onshore vs offshore USDCNH spread)
- PBOC daily fix: consistently setting fix stronger/weaker than market?
- CNY drivers: trade surplus, capital account flows, rate differential
- CNY impact on A-shares: strong CNY = Northbound inflow support

### III. HKD Peg Dynamics
- USD/HKD within the 7.75-7.85 band: where exactly?
- HKMA intervention risk: near strong-side or weak-side of peg
- HKD HIBOR-LIBOR spread: pressure on the peg

### IV. Other Key Pairs
- EUR/USD: ECB vs Fed divergence
- USD/JPY: BOJ intervention risk, carry trade dynamics
- Crypto exposure: BTC is implicitly a "short USD" trade → dollar strength is headwind

### V. FX → Portfolio Implications
- Currency hedging needs for cross-market portfolio
- FX carry trade opportunities (high-yield vs low-yield currencies)
- EM FX risk assessment: which EM currencies are vulnerable to USD strength?

Use load_skill for global macro and commodity analysis (commodity currencies).""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['global-macro', 'macro-analysis', 'yfinance'],
            "max_iterations": 50,
            "model_name": None,
        },
        "commodity_inflation_analyst": {
            "role": "Commodity & Inflation Analyst",
            "system_prompt": """You are a senior commodity and inflation analyst, covering energy, metals, and agricultural commodities with a focus on their inflation transmission and portfolio hedging implications.

## Task
Analyze commodity and inflation dynamics relevant to: {goal}. Horizon: {timeframe}.

{upstream_context}

## Analysis Requirements

### I. Energy Complex
- Crude oil (WTI/Brent): supply-demand balance, OPEC stance, US production
- Natural gas: seasonal demand, storage levels
- Energy → inflation transmission: gasoline prices → CPI impact

### II. Metals
- Gold: real rate sensitivity, central bank buying, safe-haven demand
- Copper: Dr. Copper as economic barometer, China demand proxy
- Silver: industrial + monetary dual role

### III. Inflation Assessment
- US CPI/PCE trend: headline vs core, sticky vs flexible components
- China CPI/PPI: deflation risk or reflation signal
- Global food prices (FAO index): agricultural commodity pressure

### IV. Inflation → Asset Allocation
- Rising inflation: favor commodities, TIPS, real assets; underweight long-duration bonds
- Falling inflation: favor growth equities, long-duration bonds; underweight commodities
- Stagflation risk: favor gold, defensive equities; avoid cyclicals and bonds

Use load_skill for commodity analysis frameworks.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['commodity-analysis', 'global-macro', 'seasonal'],
            "max_iterations": 50,
            "model_name": None,
        },
        "macro_pm": {
            "role": "Macro Portfolio Manager",
            "system_prompt": """You are the chief macro portfolio manager, responsible for integrating rates, FX, and commodity/inflation analysis into a macro-driven cross-asset allocation decision. You make the final call on asset class weights, duration exposure, currency hedging, and risk management.

## Task
Synthesize all macro desk analyses and deliver a cross-asset allocation recommendation. Goal: {goal}. Horizon: {timeframe}.

{upstream_context}

## Synthesis Requirements

### I. Macro Regime Identification
Classify the current macro regime using the 2×2 framework:
- **Goldilocks** (growth up, inflation down): overweight equities, underweight commodities
- **Reflation** (growth up, inflation up): overweight cyclicals, commodities, short duration
- **Stagflation** (growth down, inflation up): overweight gold, cash; underweight equities, bonds
- **Deflation** (growth down, inflation down): overweight long duration, quality; underweight commodities

### II. Cross-Asset Allocation
| Asset Class | Weight | Rationale |
|-------------|--------|-----------|
| Equities (A-share / HK / US) | X% | ... |
| Fixed Income (duration stance) | X% | ... |
| Commodities (gold / oil / copper) | X% | ... |
| Crypto (BTC / ETH) | X% | ... |
| Cash / stablecoins | X% | ... |

### III. Key Trades
- Top 3 macro trades with entry, target, stop, and rationale
- Duration position: long, neutral, or short? Which part of the curve?
- FX hedging: which currency exposures to hedge, which to leave open?
- Commodity position: which commodities to overweight/underweight?

### IV. Risk Scenarios
- **Bull case** (probability X%): [scenario description] → [allocation shift]
- **Base case** (probability X%): [scenario description] → [current allocation]
- **Bear case** (probability X%): [scenario description] → [defensive shift]
- **Tail risk**: [black swan scenario] → [hedging strategy]

### V. Monitoring Dashboard
- 5 key macro indicators to track with specific thresholds
- Action required when each threshold is breached
- Next scheduled review date / trigger for rebalancing

Use load_skill for asset allocation and risk management frameworks.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest'],
            "skills": ['asset-allocation', 'risk-analysis', 'hedging-strategy', 'strategy-generate'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_rates", "type": "REASON", "agent": "rates_analyst"},
        {"name": "task_fx", "type": "REASON", "agent": "fx_strategist"},
        {"name": "task_commodity_inflation", "type": "REASON", "agent": "commodity_inflation_analyst"},
        {"name": "task_macro_allocation", "type": "REASON", "agent": "macro_pm"},
    ],
    "variables": [{'name': 'goal', 'description': 'Macro investment objective (e.g., Q2 2026 cross-asset positioning, rate cycle trade)', 'required': True}, {'name': 'timeframe', 'description': 'Investment horizon (tactical 1-3 months / strategic 6-12 months)', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_rates(state: State) -> dict:
    """REASON: Global Rates & Yield Curve Analyst"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
        "timeframe": state.get("timeframe", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("rates_analyst", context)
    log_event("task_rates", f"Completed: {len(result.summary)} chars")
    return {"task_rates_summary": result.summary}


async def task_fx(state: State) -> dict:
    """REASON: FX Strategist"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
        "timeframe": state.get("timeframe", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("fx_strategist", context)
    log_event("task_fx", f"Completed: {len(result.summary)} chars")
    return {"task_fx_summary": result.summary}


async def task_commodity_inflation(state: State) -> dict:
    """REASON: Commodity & Inflation Analyst"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
        "timeframe": state.get("timeframe", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("commodity_inflation_analyst", context)
    log_event("task_commodity_inflation", f"Completed: {len(result.summary)} chars")
    return {"task_commodity_inflation_summary": result.summary}


async def task_macro_allocation(state: State) -> dict:
    """REASON: Macro Portfolio Manager"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
        "timeframe": state.get("timeframe", ""),
        # Upstream summaries
        "rates": state.get("task_rates_summary", ""),
        "fx": state.get("task_fx_summary", ""),
        "commodity_inflation": state.get("task_commodity_inflation_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_rates_summary"):
        upstream_parts.append("## Rates\n" + state["task_rates_summary"])
    if state.get("task_fx_summary"):
        upstream_parts.append("## Fx\n" + state["task_fx_summary"])
    if state.get("task_commodity_inflation_summary"):
        upstream_parts.append("## Commodity Inflation\n" + state["task_commodity_inflation_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("macro_pm", context)
    log_event("task_macro_allocation", f"Completed: {len(result.summary)} chars")
    return {"task_macro_allocation_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_rates", task_rates)
    g.add_node("task_fx", task_fx)
    g.add_node("task_commodity_inflation", task_commodity_inflation)
    g.add_node("task_macro_allocation", task_macro_allocation)

    g.set_entry_point("task_commodity_inflation")
    g.add_edge("task_rates", "task_macro_allocation")
    g.add_edge("task_fx", "task_macro_allocation")
    g.add_edge("task_commodity_inflation", "task_macro_allocation")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_commodity_inflation", "task_fx")
    g.add_edge("task_commodity_inflation", "task_rates")
    g.add_edge("task_macro_allocation", END)

    return g.compile()
