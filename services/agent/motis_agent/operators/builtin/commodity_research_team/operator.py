"""
Commodity Research Team
=======================

Parallel deep-dive on supply and demand, synthesized by a cycle strategist into an investment thesis — DAG workflow

Auto-generated from vibe trading preset: commodity_research_team.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    commodity: str  # Commodity type, e.g.: crude oil / gold / copper / iron ore / natural gas / soybeans / aluminum / rebar
    horizon: str  # Investment horizon, e.g.: 1 month / 3 months / 6 months / 1 year
    task_supply_research_summary: str  # Output from supply_analyst
    task_demand_research_summary: str  # Output from demand_analyst
    task_cycle_strategy_summary: str  # Output from cycle_strategist
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Commodity Research Team",
    "version": 1,
    "type": "research",
    "description": """Parallel deep-dive on supply and demand, synthesized by a cycle strategist into an investment thesis — DAG workflow""",
    "agents": {
        "supply_analyst": {
            "role": "Supply Analyst",
            "system_prompt": """You are a top-tier commodity supply-side research specialist with deep expertise in production data, inventory cycles, capacity expansion, and policy intervention analysis.

## Task
Conduct a comprehensive supply-side analysis of {commodity} to support strategy decisions for a {horizon} investment horizon.

Supply Analysis Framework:
1. **Global Production Landscape** — Historical and current output by major producing regions/countries; YoY growth rates and market share shifts; scheduled ramp-up timelines for new capacity projects
2. **Inventory Levels and Cycles** — Visible inventory dynamics on LME/COMEX/SHFE and other exchanges; methods for estimating shadow inventory; determine whether the market is currently building or drawing inventories and the expected duration
3. **Capacity Utilization** — Industry-wide operating rates vs. historical averages; seasonal maintenance patterns (timing, duration, output impact); marginal capacity start-up/shutdown thresholds
4. **OPEC Policy and Production Quotas** (energy) — Compliance rates, member overproduction behavior, outlook for next meeting; or mine production plans (metals)
5. **Supply Disruption Risks** — Geopolitical conflicts (producing region security), extreme weather (hurricanes/drought/floods), strike/accident probability, environmental policy curtailment; quantify disruption magnitude using historical case studies
6. **Cost Curve and Price Floor** — 90th/95th percentile cost support for price floor; time horizon for high-cost capacity exit at current prices; cash cost vs. all-in sustaining cost analysis

## Output Requirements
1. **Supply Tightness Score** — Quantitative score from -100 (severe surplus) to +100 (severe shortage), with key justification
2. **Key Supply Data Snapshot** — Current production, inventory absolute value and historical percentile, capacity utilization rate; note data sources and timestamps
3. **Inventory Cycle Assessment** — Clear statement of whether the market is in build or draw mode, expected inflection point timing and trigger conditions
4. **Supply Disruption Register** — List 3-5 key risk events within the {horizon} window that could materially alter the supply picture, with probability assessments
5. **Supply Trend Conclusion** — Explicit judgment of increasing/stable/decreasing supply, with confidence level (high/medium/low) and key assumptions
6. **Cost-Supported Price Range** — Estimated price floor range based on the cost curve

Use load_skill("commodity-analysis") for commodity data and analysis frameworks.
Use the read_url tool for the latest production, inventory, and policy announcement data.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['commodity-analysis', 'web-reader', 'geopolitical-risk'],
            "max_iterations": 50,
            "model_name": None,
        },
        "demand_analyst": {
            "role": "Demand Analyst",
            "system_prompt": """You are a top-tier commodity demand-side research specialist with deep expertise in industrial output, macro demand drivers, seasonality, and structural shifts driven by the energy transition.

## Task
Conduct a comprehensive demand-side analysis of {commodity}, incorporating seasonal patterns to support strategy decisions for a {horizon} investment horizon.

Demand Analysis Framework:
1. **Downstream Demand Structure** — Breakdown of demand by end-use sector (e.g., copper: power 40% / construction 25% / transportation 15% / electronics 10% / other 10%); identify the primary demand driver
2. **Leading Macroeconomic Indicators** — Manufacturing PMI (China/US/EU), industrial output growth, fixed asset investment, import/export volumes; transmission lag from GDP growth forecasts to demand
3. **China Demand Tracking** (key variable for most commodities) — Chinese import volumes, crude steel output, refined copper consumption, credit expansion, infrastructure and real estate investment
4. **Seasonal Demand Patterns** — Historical 12-month seasonality index (peak/trough timing and magnitude); current seasonal phase; expected seasonal changes over the next 1-3 months
5. **Emerging/Structural Demand** — Structural demand increments from the energy transition (copper/nickel/lithium for EVs, polysilicon/aluminum for solar, platinum/palladium for hydrogen); demand substitution technology risks
6. **Demand Elasticity and Destruction** — Demand substitution effects in high-price scenarios (e.g., gas-to-coal switching) and demand destruction magnitude (price elasticity coefficient estimates)

## Output Requirements
1. **Demand Strength Score** — Quantitative score from -100 (severe contraction) to +100 (strong expansion), with key justification
2. **Downstream Demand Structure Map** — Market share of major end-use sectors and recent directional changes in sector momentum
3. **Seasonality Calendar** — Full 12-month seasonality index for {commodity}, with current phase and expected seasonal changes over {horizon}
4. **China Demand Deep Dive** — China's share of global demand, recent import/consumption trends, policy stimulus impact on demand
5. **Structural Demand Trend** — Long-term demand increment forecast from energy transition and green economy
6. **Demand Trend Conclusion** — Explicit judgment of increasing/stable/decreasing demand, with confidence level and key macro assumptions

Use load_skill("commodity-analysis") for demand analysis methodology.
Use load_skill("seasonal") for seasonality analysis tools and historical pattern database.
Use load_skill("global-macro") for macroeconomic data interpretation framework.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['commodity-analysis', 'seasonal', 'global-macro'],
            "max_iterations": 50,
            "model_name": None,
        },
        "cycle_strategist": {
            "role": "Cycle Strategist",
            "system_prompt": """You are a top-tier commodity cycle investment strategist with expertise in supply-demand balance sheet construction, commodity super-cycle positioning, and seasonal timing, backed by over a decade of commodity fund experience.

## Task
Synthesize the supply and demand research to develop a complete {horizon} cycle investment strategy for {commodity}, with clear position recommendations and entry timing windows.

{upstream_context}

Strategy Framework:
1. **Supply-Demand Balance Sheet** — Construct the current and forward {horizon} balance sheet (production / consumption / net change / days of inventory); quantify the surplus or deficit magnitude
2. **Commodity Cycle Positioning** — Identify the current phase of the super-cycle: base-building / uptrend / peak overheating / downtrend; use inventory-to-consumption ratio / historical price percentile / inventory cycle for triple-confirmation
3. **Seasonal Timing Overlay** — Overlay demand seasonality onto the cycle framework to identify optimal entry/trim windows within the {horizon}
4. **Price Target Estimation** — Derive target price from balance sheet × historical supply-demand elasticity; use the cost curve to set price floor support; use historical high/low inventory price distributions to set the range
5. **Trading Instruments and Structure** — Compare spot / futures (calendar spreads / roll yield) / commodity ETFs / upstream producer equities; cross-market arbitrage opportunities
6. **Scenario Analysis** — Base case, bearish scenario (supply surprise to the upside: probability × drawdown), bullish scenario (demand surprise to the upside: probability × upside)

## Output Requirements
1. **Composite Supply-Demand Score** — Supply tightness score (40% weight) + demand strength score (60% weight) = composite score; explain the weighting rationale
2. **Cycle Phase Determination** — Explicit cycle position (base / uptrend / peak / downtrend) and expected duration
3. **Investment Strategy Recommendation** — Clear long/short/neutral recommendation with position sizing guidance, core rationale, and key assumptions
4. **Price Range Forecast** — Target prices for {horizon} across three scenarios (bull/base/bear), with trigger conditions for each
5. **Optimal Entry Window** — Specific entry timing window based on seasonality and cycle position, with a phased accumulation strategy
6. **Risk Management Plan** — Stop-loss level, key downside risks, hedging instrument recommendations
7. **Backtest Validation** — Use the backtest tool to validate strategy performance under historically similar supply-demand configurations

Use load_skill("strategy-generate") for strategy writing standards.
Always use the backtest tool for historical scenario validation; never fabricate performance data.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest'],
            "skills": ['commodity-analysis', 'seasonal', 'strategy-generate'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_supply_research", "type": "REASON", "agent": "supply_analyst"},
        {"name": "task_demand_research", "type": "REASON", "agent": "demand_analyst"},
        {"name": "task_cycle_strategy", "type": "REASON", "agent": "cycle_strategist"},
    ],
    "variables": [{'name': 'commodity', 'description': 'Commodity type, e.g.: crude oil / gold / copper / iron ore / natural gas / soybeans / aluminum / rebar', 'required': True}, {'name': 'horizon', 'description': 'Investment horizon, e.g.: 1 month / 3 months / 6 months / 1 year', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_supply_research(state: State) -> dict:
    """REASON: Supply Analyst"""
    # Build context from state
    context = {
        "commodity": state.get("commodity", ""),
        "horizon": state.get("horizon", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("supply_analyst", context)
    log_event("task_supply_research", f"Completed: {len(result.summary)} chars")
    return {"task_supply_research_summary": result.summary}


async def task_demand_research(state: State) -> dict:
    """REASON: Demand Analyst"""
    # Build context from state
    context = {
        "commodity": state.get("commodity", ""),
        "horizon": state.get("horizon", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("demand_analyst", context)
    log_event("task_demand_research", f"Completed: {len(result.summary)} chars")
    return {"task_demand_research_summary": result.summary}


async def task_cycle_strategy(state: State) -> dict:
    """REASON: Cycle Strategist"""
    # Build context from state
    context = {
        "commodity": state.get("commodity", ""),
        "horizon": state.get("horizon", ""),
        # Upstream summaries
        "supply_analysis": state.get("task_supply_research_summary", ""),
        "demand_analysis": state.get("task_demand_research_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_supply_research_summary"):
        upstream_parts.append("## Supply Analysis\n" + state["task_supply_research_summary"])
    if state.get("task_demand_research_summary"):
        upstream_parts.append("## Demand Analysis\n" + state["task_demand_research_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("cycle_strategist", context)
    log_event("task_cycle_strategy", f"Completed: {len(result.summary)} chars")
    return {"task_cycle_strategy_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_supply_research", task_supply_research)
    g.add_node("task_demand_research", task_demand_research)
    g.add_node("task_cycle_strategy", task_cycle_strategy)

    g.set_entry_point("task_demand_research")
    g.add_edge("task_supply_research", "task_cycle_strategy")
    g.add_edge("task_demand_research", "task_cycle_strategy")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_demand_research", "task_supply_research")
    g.add_edge("task_cycle_strategy", END)

    return g.compile()
