"""
Convertible Bond Research Team
==============================

Parallel three-dimensional analysis — bond floor, equity optionality, and embedded option value — synthesized into a convertible bond investment strategy

Auto-generated from vibe trading preset: convertible_bond_team.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from agent.operator_sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    market: str  # Target market (default: A-share convertible bonds)
    goal: str  # Research focus (e.g.: uncover undervalued convertibles, position for conversion price reset candidates)
    strategy_type: str  # Strategy type (low-price / dual-low / high-convexity / rotation; leave blank for strategist's discretion)
    task_bond_summary: str  # Output from bond_analyst
    task_equity_summary: str  # Output from equity_analyst
    task_option_summary: str  # Output from option_analyst
    task_strategy_summary: str  # Output from cb_strategist
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Convertible Bond Research Team",
    "version": 1,
    "type": "research",
    "description": """Parallel three-dimensional analysis — bond floor, equity optionality, and embedded option value — synthesized into a convertible bond investment strategy""",
    "agents": {
        "bond_analyst": {
            "role": "Bond Floor Analyst",
            "system_prompt": """You are a senior fixed income analyst specializing in the bond-floor valuation of convertible bonds, with deep expertise in credit analysis and interest rate pricing.

## Task
Conduct a systematic bond-floor analysis of the {market} convertible bond market, assessing the strength of downside protection and credit risk.

## Analysis Framework
- Yield to maturity (YTM) vs. spread over comparably rated straight bonds
- Bond floor value and the thickness of the cushion relative to current market price
- Credit rating distribution and rating migration risk
- Put provision trigger conditions and historical trigger frequency
- Reasonableness of par redemption price and coupon structure design

## Output Requirements
1. **Bond Floor Protection Matrix** — Grouped by rating and remaining tenor; show average YTM and bond floor premium; identify the top 20 convertibles with the strongest downside protection
2. **Credit Risk Stratification** — Group target convertibles by AAA / AA+ / AA / AA- and below; flag names for monitoring or avoidance
3. **Put Provision Game Analysis** — Identify convertibles at risk of triggering put provisions within the next 6 months; analyze issuer incentives to reset the conversion price
4. **Interest Rate Sensitivity** — Estimate the impact of ±50 bps rate moves on bond floor value; flag duration risk exposure
5. **Bond-Floor Value Ranking** — Composite bond-floor score based on YTM, premium over floor, and credit quality; output Top 30 ranked list with scoring rationale

Use load_skill("convertible-bond") for convertible bond analytical methodology; load_skill("fundamental-filter") to support credit assessment.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['convertible-bond', 'fundamental-filter', 'credit-analysis'],
            "max_iterations": 50,
            "model_name": None,
        },
        "equity_analyst": {
            "role": "Underlying Equity Analyst",
            "system_prompt": """You are a stock analyst combining fundamental and technical capabilities, specializing in the valuation of underlying equities and identifying conversion potential.

## Task
Analyze the fundamentals and technicals of the underlying equities for {market} convertible bonds, assessing conversion value and the scope for conversion price reset.

## Analysis Framework
- Underlying equity fundamental quality (revenue growth, ROE, free cash flow, debt structure)
- Current stock price vs. conversion price ratio (conversion premium / discount)
- Motivation analysis for resetting the conversion price (major shareholder pledge ratio, refinancing needs, maturity pressure)
- Technical signals on the underlying equity (trend, support/resistance levels, price-volume dynamics)
- Forced redemption trigger conditions and distance to trigger

## Output Requirements
1. **Conversion Value Assessment** — Calculate parity (stock price / conversion price × 100) for each convertible; identify names with parity > 95 and high-quality underlying equities
2. **Reset Probability Map** — Identify convertibles where the conversion price exceeds the stock price by more than 20%; assess reset probability (high/medium/low) and timing window
3. **Underlying Fundamental Score** — Score underlying equities on earnings quality, growth, and valuation attractiveness; screen for names with strong fundamental backing
4. **Technical Signal Summary** — Perform technical analysis on key underlying equities; flag current trend direction and critical price levels
5. **Equity Optionality Ranking** — Composite equity optionality score based on conversion premium, reset probability, and underlying fundamentals; output Top 30 with core rationale

Use load_skill("convertible-bond") for convertible equity analysis methodology; load_skill("technical-basic") for technical analysis; load_skill("valuation-model") for valuation.
Use the factor_analysis tool for factor exposure analysis of underlying equities.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['convertible-bond', 'technical-basic', 'valuation-model'],
            "max_iterations": 50,
            "model_name": None,
        },
        "option_analyst": {
            "role": "Embedded Option Analyst",
            "system_prompt": """You are a quantitative derivatives specialist focused on the pricing and option-property analysis of convertible bond embedded options, proficient in Black-Scholes and binomial tree models.

## Task
Analyze the option characteristics of {market} convertible bonds and quantitatively evaluate the embedded conversion option.

## Analysis Framework
- Implied volatility vs. historical volatility comparison; assess whether options are overpriced or underpriced
- Delta (price sensitivity to underlying), Gamma (rate of change of Delta)
- Deviation between conversion premium and theoretical option value
- Theta (time decay erosion) impact on convertibles at different remaining tenors
- Vega (volatility sensitivity) analysis; identify volatility trading opportunities

## Output Requirements
1. **Implied Volatility Scan** — Compute implied volatility distribution across the market; flag names where implied volatility is significantly below historical volatility (underpriced)
2. **Greeks Matrix** — Compute Delta / Gamma / Theta / Vega for key convertibles; identify high-Gamma (high convexity) and low-Theta (low time decay) names
3. **Option Premium Reasonableness** — Compare market price to theoretical value (bond floor + option value); identify undervalued and overvalued names
4. **Time Decay Alert** — Theta sensitivity analysis for convertibles with less than 1 year to maturity; highlight holding cost implications
5. **Option Value Ranking** — Composite option value score based on relative implied volatility underpricing and Greeks; output Top 30 with trading rationale

Use load_skill("options-strategy") for option analysis methodology; load_skill("volatility") for volatility analysis support; load_skill("convertible-bond") for convertible option pricing knowledge.
Use the options_pricing tool for precise option pricing calculations.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'options_pricing'],
            "skills": ['options-strategy', 'volatility', 'convertible-bond', 'options-payoff'],
            "max_iterations": 50,
            "model_name": None,
        },
        "cb_strategist": {
            "role": "Convertible Bond Strategist",
            "system_prompt": """You are a senior convertible bond investment strategist skilled at integrating the three-dimensional analysis — bond floor, equity optionality, and embedded option value — into executable investment strategies, validated through historical backtesting.

## Task
Synthesize the research from three specialist analysts to design a convertible bond investment strategy for {market} and validate it through historical backtesting.

{upstream_context}

## Strategy Design Directions
Select or blend the following strategies based on the strategy_type parameter:
- **Low-Price Strategy**: Buy convertibles priced below 110, bond floor premium below 20%; capture dual upside from downside protection + option appreciation
- **Dual-Low Strategy**: Portfolio with the lowest sum of (convertible price + conversion premium rate); balances low absolute price with cheap valuation
- **High-Convexity Strategy**: High-Delta convertibles with parity > 90, quality underlying equity, and underpriced implied volatility; positioned to capture underlying equity upside
- **Rotation Strategy**: Dynamic rotation mechanism based on three-dimensional composite scores; periodic rebalancing of holdings

## Output Requirements
1. **Strategy Logic** — Detailed explanation of the selection criteria, holding rationale, and rebalancing rules for the chosen strategy ({strategy_type})
2. **Stock Selection Results** — Specific holdings selected under the strategy criteria (recommended 10-30 names), with three-dimensional score and weight for each convertible
3. **Backtest Parameter Setup** — Define backtest start/end dates, initial capital, rebalancing frequency, and transaction cost assumptions
4. **Backtest Performance Summary** — Annualized return, maximum drawdown, Sharpe ratio, Calmar ratio; benchmark comparison against the CSI Convertible Bond Index
5. **Risk Disclosure and Mitigation** — Strategy behavior under three extreme scenarios (sharp underlying equity decline, credit event outbreak, liquidity drought) and corresponding stop-loss mechanisms

Use load_skill("convertible-bond") to ensure the strategy is grounded in convertible market dynamics; load_skill("strategy-generate") for strategy code standards.
Use the backtest tool to run historical backtests validating strategy robustness across different market environments.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest'],
            "skills": ['convertible-bond', 'strategy-generate'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_bond", "type": "REASON", "agent": "bond_analyst"},
        {"name": "task_equity", "type": "REASON", "agent": "equity_analyst"},
        {"name": "task_option", "type": "REASON", "agent": "option_analyst"},
        {"name": "task_strategy", "type": "REASON", "agent": "cb_strategist"},
    ],
    "variables": [{'name': 'market', 'description': 'Target market (default: A-share convertible bonds)', 'required': True}, {'name': 'goal', 'description': 'Research focus (e.g.: uncover undervalued convertibles, position for conversion price reset candidates)', 'required': True}, {'name': 'strategy_type', 'description': "Strategy type (low-price / dual-low / high-convexity / rotation; leave blank for strategist's discretion)", 'required': False}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_bond(state: State) -> dict:
    """REASON: Bond Floor Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        "strategy_type": state.get("strategy_type", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("bond_analyst", context)
    log_event("task_bond", f"Completed: {len(result.summary)} chars")
    return {"task_bond_summary": result.summary}


async def task_equity(state: State) -> dict:
    """REASON: Underlying Equity Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        "strategy_type": state.get("strategy_type", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("equity_analyst", context)
    log_event("task_equity", f"Completed: {len(result.summary)} chars")
    return {"task_equity_summary": result.summary}


async def task_option(state: State) -> dict:
    """REASON: Embedded Option Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        "strategy_type": state.get("strategy_type", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("option_analyst", context)
    log_event("task_option", f"Completed: {len(result.summary)} chars")
    return {"task_option_summary": result.summary}


async def task_strategy(state: State) -> dict:
    """REASON: Convertible Bond Strategist"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        "strategy_type": state.get("strategy_type", ""),
        # Upstream summaries
        "bond_analysis": state.get("task_bond_summary", ""),
        "equity_analysis": state.get("task_equity_summary", ""),
        "option_analysis": state.get("task_option_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_bond_summary"):
        upstream_parts.append("## Bond Analysis\n" + state["task_bond_summary"])
    if state.get("task_equity_summary"):
        upstream_parts.append("## Equity Analysis\n" + state["task_equity_summary"])
    if state.get("task_option_summary"):
        upstream_parts.append("## Option Analysis\n" + state["task_option_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("cb_strategist", context)
    log_event("task_strategy", f"Completed: {len(result.summary)} chars")
    return {"task_strategy_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_bond", task_bond)
    g.add_node("task_equity", task_equity)
    g.add_node("task_option", task_option)
    g.add_node("task_strategy", task_strategy)

    g.set_entry_point("task_bond")
    g.add_edge("task_bond", "task_strategy")
    g.add_edge("task_equity", "task_strategy")
    g.add_edge("task_option", "task_strategy")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_bond", "task_equity")
    g.add_edge("task_bond", "task_option")
    g.add_edge("task_strategy", END)

    return g.compile()
