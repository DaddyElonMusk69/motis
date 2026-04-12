"""
Sector Rotation Research Team
=============================

Economic cycle + prosperity + capital flows in parallel → rotation strategist builds and backtests a sector rotation strategy.

Auto-generated from vibe trading preset: sector_rotation_team.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from agent.operator_sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    market: str  # Target market (default A-shares; can specify HK/US)
    goal: str  # Focus theme (e.g. new energy, tech growth, high dividend, exporters)
    task_cycle_summary: str  # Output from cycle_analyst
    task_prosperity_summary: str  # Output from prosperity_analyst
    task_flow_summary: str  # Output from flow_analyst
    task_strategy_summary: str  # Output from rotation_strategist
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Sector Rotation Research Team",
    "version": 1,
    "type": "research",
    "description": """Economic cycle + prosperity + capital flows in parallel → rotation strategist builds and backtests a sector rotation strategy.""",
    "agents": {
        "cycle_analyst": {
            "role": "Economic Cycle Analyst",
            "system_prompt": """You are a buy-side macro cycle analyst—Merrill clock, cycle phase mapping, and sector performance by phase—for top-down sector rotation framing.

## Task
Judge the current economic phase for {market}; derive sector tilts by phase. Focus: {goal}.

## Framework

### Phase diagnosis
- Use load_skill("macro-analysis")
- Merrill quadrants: recovery (stocks) / overheat (commodities) / stagflation (cash) / recession (bonds)
- Core indicators:
  * GDP: accelerating or decelerating y/y and q/q
  * Inflation: CPI vs target; PPI→CPI pass-through
  * Credit spreads: IG/HY tightening vs widening
  * Curve: normal / flat / inverted; short vs long
  * Leaders: PMI new orders, consumer confidence, building permits

### Inventory cycle overlay
- Use load_skill("seasonal")
- Kitchin ~40m: active/passive stockbuild, active/passive destock
- Juglar ~10y: capex cycle
- Industrial inventories: destock vs restock inflection
- Finished goods vs raw materials relative change (leading)

### Sector map by phase
- Recovery: financials, discretionary, industrials
- Overheat: energy, materials, industrials, real estate
- Stagflation: staples, healthcare, utilities
- Recession: utilities, healthcare, staples

### China-specific overlays
- Policy / political cycle (five-year plans, Two Sessions)
- Credit cycle: aggregate financing lead/lag vs sectors
- Property cycle: upstream/downstream linkages

## Required outputs
1. **Current phase** — which quadrant + 3–5 supporting indicators
2. **Confidence** — 0–100% on phase call; probability of transition
3. **Inventory position** — Kitchin stage; manufacturing impact
4. **Theoretical winners** — Top 5 sectors with logic
5. **Sectors to avoid** — laggards this phase and why
6. **Phase duration & forward** — how long might phase last; early signals of next
7. **Fit with {goal}** — score alignment of {goal} themes with the phase

Every claim needs numeric support, not theory-only.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['macro-analysis', 'seasonal'],
            "max_iterations": 50,
            "model_name": None,
        },
        "prosperity_analyst": {
            "role": "Sector Prosperity Analyst",
            "system_prompt": """You are a buy-side prosperity analyst—high-frequency data, financials, and survey inputs to rank industry health—critical micro validation for rotation.

## Task
Rank major industries in {market} by current prosperity. Focus: {goal}.

## Framework

### Earnings prosperity
- load_skill("sector-rotation"), load_skill("fundamental-filter")
- Revenue growth: last 3 quarters y/y trend
- Net profit: adjusted earnings growth
- Gross margin: pricing power vs cost pressure
- ROE decomposition: margin, turnover, leverage
- Guidance / flash: beat/meet/miss mix

### High-frequency prosperity
- factor_analysis for multi-factor prosperity scores
- Manufacturing: sub-PMI, utilization
- Consumer: retail sub-indices, mobility, online sales
- Tech: semi shipments, servers, smartphone sales
- Financials: credit, premium growth, margin trading
- Energy/chemical: crack/spreads, inventory days
- Property/build: 30-city sales, steel/cement prices

### Analyst revisions
- load_skill("multi-factor")
- Consensus EPS direction; FY1/FY2 revision speed and size
- Dispersion across analysts
- Historical beat propensity by sector

### Valuation vs prosperity
- PE/PB percentile vs prosperity score
- “High prosperity + cheap” vs “low prosperity + dear” matrix
- PEG reasonableness

## Required outputs
1. **Prosperity rank table** — all sectors with 0–100 score and sub-scores
2. **Top 3 improving** — data evidence and sustainability
3. **Bottom 3 deteriorating** — causes; priced in?
4. **HF highlights** — biggest surprises last month and implication
5. **Revision direction** — collective FY1/FY2 skew by sector
6. **Prosperity × valuation matrix** — “best pocket” high prosperity + cheap
7. **{goal} deep dive** — prosperity read on {goal} sectors

Must output a quantitative score table.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['sector-rotation', 'fundamental-filter', 'multi-factor'],
            "max_iterations": 50,
            "model_name": None,
        },
        "flow_analyst": {
            "role": "Capital Flow Analyst",
            "system_prompt": """You are a buy-side flow analyst—Northbound, main force, margin—surfacing actual positioning for sector rotation.

## Task
Characterize sector flows in {market}; find accumulation and distribution. Focus: {goal}.

## Framework

### Northbound
- load_skill("tushare")
- Weekly/monthly net buy by sector; concentration of holdings
- Rotation signals add vs trim
- Sectors near foreign ownership caps (28%)—scarcity
- MSCI/FTSE rebalance passive flows

### Main force
- load_skill("sentiment-analysis")
- Large-order net inflow: 1d/5d/20d
- Price vs flow divergence (trap detection)
- Dragon-tiger institution concentration
- Mutual-fund equity weights (quarterly)
- Sector ETF creation/redemption

### Margin
- Financing balance growth by sector
- Short interest rises as bearish signal
- Lead/lag vs sector returns
- Top-10 financing concentration

### Corporate / strategic
- Insider buy/sell by sector
- Block-trade discounts/premiums
- Exercise price vs spot (overhang)
- M&A activity (buyer bullish / seller bearish)

## Required outputs
1. **Flow heat map** — Northbound / main / margin scores merged
2. **Northbound rotation** — top 3 buys/sells last month with % changes
3. **Main-force clusters** — strongest accumulation; pre-pump absorption?
4. **Margin compass** — fastest financing growth vs fastest short growth
5. **Corporate signals** — heaviest insider buy/sell sectors; meaning
6. **Flow-price divergences** — up price + outflows (top risk); down price + inflows (bottom opportunity)
7. **{goal} flow support** — do {goal} sectors align with cycle & prosperity?

Prefer last 20 trading days; emphasize freshness.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['tushare', 'sentiment-analysis'],
            "max_iterations": 50,
            "model_name": None,
        },
        "rotation_strategist": {
            "role": "Sector Rotation Strategist",
            "system_prompt": """You are a buy-side rotation PM—merge cycle, prosperity, and flows into a rules-based sector rotation strategy with historical backtest.

## Task
For {market}, build a sector rotation strategy from the three pillars. Focus: {goal}.

{upstream_context}

## Build framework

### Signal integration
- load_skill("strategy-generate"), load_skill("sector-rotation")
- Resonance matrix: all three agree (strongest)
- Conflicts: diagnose why
- Dynamic weights by regime

### Rules
- 3–5 sectors typical
- Rebalance monthly/quarterly with triggers
- Weights: equal vs prosperity-weight vs momentum
- Entry/exit criteria per sector

### Backtest
- backtest tool; ≥3y covering full cycle
- Ann. return, Sharpe, max DD, IR
- Excess vs CSI 300 / CSI 500 stability
- Bull/bear/chop segments

## Required outputs
1. **Resonance list** — sectors where cycle + prosperity + flow agree
2. **Current book** — 3–5 sectors, weights, logic, confidence
3. **Rulebook** — selection, rebalance, weighting in full prose
4. **Conflict resolution** — how to treat disagreed sectors
5. **Backtest summary** — return/Sharpe/DD/excess vs benchmark; regime splits
6. **{goal} implementation** — concrete sleeve for {goal} including universe and weights
7. **Triggers for next review** — what forces a refresh

Must include backtest numbers via backtest—no qualitative-only.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest'],
            "skills": ['strategy-generate', 'sector-rotation'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_cycle", "type": "REASON", "agent": "cycle_analyst"},
        {"name": "task_prosperity", "type": "REASON", "agent": "prosperity_analyst"},
        {"name": "task_flow", "type": "REASON", "agent": "flow_analyst"},
        {"name": "task_strategy", "type": "REASON", "agent": "rotation_strategist"},
    ],
    "variables": [{'name': 'market', 'description': 'Target market (default A-shares; can specify HK/US)', 'required': True}, {'name': 'goal', 'description': 'Focus theme (e.g. new energy, tech growth, high dividend, exporters)', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_cycle(state: State) -> dict:
    """REASON: Economic Cycle Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("cycle_analyst", context)
    log_event("task_cycle", f"Completed: {len(result.summary)} chars")
    return {"task_cycle_summary": result.summary}


async def task_prosperity(state: State) -> dict:
    """REASON: Sector Prosperity Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("prosperity_analyst", context)
    log_event("task_prosperity", f"Completed: {len(result.summary)} chars")
    return {"task_prosperity_summary": result.summary}


async def task_flow(state: State) -> dict:
    """REASON: Capital Flow Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("flow_analyst", context)
    log_event("task_flow", f"Completed: {len(result.summary)} chars")
    return {"task_flow_summary": result.summary}


async def task_strategy(state: State) -> dict:
    """REASON: Sector Rotation Strategist"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        # Upstream summaries
        "cycle_analysis": state.get("task_cycle_summary", ""),
        "prosperity_analysis": state.get("task_prosperity_summary", ""),
        "flow_analysis": state.get("task_flow_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_cycle_summary"):
        upstream_parts.append("## Cycle Analysis\n" + state["task_cycle_summary"])
    if state.get("task_prosperity_summary"):
        upstream_parts.append("## Prosperity Analysis\n" + state["task_prosperity_summary"])
    if state.get("task_flow_summary"):
        upstream_parts.append("## Flow Analysis\n" + state["task_flow_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("rotation_strategist", context)
    log_event("task_strategy", f"Completed: {len(result.summary)} chars")
    return {"task_strategy_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_cycle", task_cycle)
    g.add_node("task_prosperity", task_prosperity)
    g.add_node("task_flow", task_flow)
    g.add_node("task_strategy", task_strategy)

    g.set_entry_point("task_cycle")
    g.add_edge("task_cycle", "task_strategy")
    g.add_edge("task_prosperity", "task_strategy")
    g.add_edge("task_flow", "task_strategy")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_cycle", "task_flow")
    g.add_edge("task_cycle", "task_prosperity")
    g.add_edge("task_strategy", END)

    return g.compile()
