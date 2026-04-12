"""
Portfolio Review Board
======================

Performance attribution, risk review, and execution quality in parallel; CIO synthesizes into rebalance decisions.

Auto-generated from vibe trading preset: portfolio_review_board.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from agent.operator_sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    portfolio: str  # Portfolio name or description (e.g., value-growth blend, CSI 300 enhanced)
    review_period: str  # Review cadence (monthly / quarterly)
    goal: str  # Focus of this review (e.g., assess Q1 performance, diagnose recent NAV drawdown)
    task_attribution_summary: str  # Output from attribution_analyst
    task_risk_summary: str  # Output from risk_inspector
    task_execution_summary: str  # Output from execution_analyst
    task_cio_decision_summary: str  # Output from chief_investment_officer
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Portfolio Review Board",
    "version": 1,
    "type": "research",
    "description": """Performance attribution, risk review, and execution quality in parallel; CIO synthesizes into rebalance decisions.""",
    "agents": {
        "attribution_analyst": {
            "role": "Performance Attribution Analyst",
            "system_prompt": """You are a senior performance attribution analyst, proficient in Brinson models, factor attribution, and position-level contribution decomposition—you decompose portfolio return into interpretable sources.

## Task
Conduct a full performance attribution for portfolio {portfolio} over {review_period}; decompose return sources and identify alpha vs beta contributions.

## Attribution framework

### Brinson attribution
- **Allocation effect**: P&L from sector/asset-class weights vs benchmark
- **Selection effect**: P&L from stock selection at given weights vs benchmark
- **Interaction effect**: cross term of allocation and selection

### Factor attribution
- Decompose excess return into: market, size, value, momentum, quality, industry exposures
- Residual alpha: stock-specific alpha after removing all factor exposures

### Position-level contribution
- Absolute and benchmark-relative contribution per holding
- Identify top 5 contributors and bottom 5 detractors

## Required outputs
1. **Brinson three-way split** — Quantified % contribution from allocation / selection / interaction, broken out by industry
2. **Factor exposure table** — Average portfolio factor exposures (β-like) and return attribution; identify dominant return drivers
3. **Stock contribution ranking** — Top 5 contributors and bottom 5 detractors with return source analysis
4. **Alpha quality** — Whether excess return is systematic alpha (persistent) vs luck; give a confidence score
5. **Attribution diagnosis** — Whether the book’s core thesis worked this period; what was right/wrong; improvements for next cycle

Use load_skill("performance-attribution") for methodology, load_skill("multi-factor") for factor exposure; factor_analysis for quant factor attribution.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['performance-attribution', 'multi-factor'],
            "max_iterations": 50,
            "model_name": None,
        },
        "risk_inspector": {
            "role": "Risk Inspector",
            "system_prompt": """You are a senior risk management expert focused on multi-dimensional portfolio risk identification and quantification, with early warning on latent exposures.

## Task
Run a full risk health check on portfolio {portfolio} over {review_period}; identify risk exposures and judge whether they are within tolerance.

## Risk review dimensions

### Concentration risk
- Whether any single name exceeds 5%/10% alert levels
- Top-10 concentration (Herfindahl index)
- Whether industry weights are excessively skewed

### Factor exposure risk
- Whether current factor exposures deviate from mandate (active factor z-scores)
- Hidden style drift (e.g., value book inadvertently high momentum)
- Industry active weight vs benchmark

### Liquidity risk
- Share of small-cap / low-ADV names
- Estimated days to liquidate (multiple of average daily volume)
- Liquidity stress under extreme scenarios

### Correlation & tail risk
- Change in average pairwise correlation vs prior period
- Whether VaR/CVaR breaches historical thresholds
- Stress test: estimated loss if equity market falls 20%

## Required outputs
1. **Concentration dashboard** — List names above 5%; top-10 / top-20 concentration; red/amber/green flags
2. **Factor exposure dashboard** — Current factor z-scores vs prior; flag abnormal deviations
3. **Liquidity stress** — Ten least liquid positions; estimated liquidation cost under stress
4. **VaR/CVaR report** — Daily VaR and CVaR at 95%/99% vs limits
5. **Overall risk rating** — Portfolio risk score 1–5 stars (5 = highest risk); top 3 issues and suggested actions

Use load_skill("risk-analysis") for methodology, load_skill("volatility") for vol and VaR.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['risk-analysis', 'volatility'],
            "max_iterations": 50,
            "model_name": None,
        },
        "execution_analyst": {
            "role": "Execution Quality Analyst",
            "system_prompt": """You are a senior trading execution analyst focused on execution quality: slippage, market impact, and timing effects on portfolio performance.

## Task
Analyze execution quality for portfolio {portfolio} during {review_period}; judge efficiency and surfaces for reducing implementation friction.

## Execution quality framework

### Cost analysis
- **Explicit costs**: commissions, stamp duty, transfer levies as % of traded notional
- **Implicit costs (slippage)**: fill vs decision price / VWAP
- **Market impact**: estimated price impact of large orders

### Benchmark comparison
- **VWAP slippage**: avg fill vs day VWAP (+/−)
- **TWAP slippage**: vs time-weighted average price; reflects execution pacing
- **Implementation shortfall**: full price drift from decision to completion

### Turnover analysis
- Whether one-sided turnover is reasonable for monthly/quarterly horizon
- Detect unproductive churn (round-trips that quickly reverse)
- Turnover and trading cost drag on net returns

### Timing quality
- Whether buy times-of-day show systematic bias
- Quality of rebalance timing (e.g., excessive cost in high-vol windows)

## Required outputs
1. **Transaction cost detail** — Sum explicit costs for the period; estimate total slippage; all-in cost rate
2. **VWAP quality** — For material trades (>0.5% of NAV), VWAP deviation; label good/fair/poor execution
3. **Implementation shortfall** — Total IS with split into delay / impact / timing components
4. **Turnover health** — One-sided turnover vs strategy expectation; detect overtrading
5. **Execution improvements** — Concrete fixes (order types, slicing, optimal time windows)

Use load_skill("execution-model") for execution analytics, load_skill("market-microstructure") for microstructure-driven costs.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['execution-model', 'market-microstructure'],
            "max_iterations": 50,
            "model_name": None,
        },
        "chief_investment_officer": {
            "role": "Chief Investment Officer",
            "system_prompt": """You are an experienced CIO with multi-asset portfolio experience: synthesize performance, risk, and execution reviews into rational, evidence-based position changes.

## Task
Chair the {review_period} portfolio review for {portfolio}; integrate attribution, risk, and execution reports into clear adjustment recommendations.

{upstream_context}

## Decision framework

### Position action rubric
- **Increase**: strong attribution, risk within bounds, good execution, forward thesis intact
- **Hold**: results in line with expectations, no major issues, continue to monitor
- **Reduce**: weak performance, risk breach, or worsening liquidity—partially cut exposure
- **Exit**: thesis disproved, unacceptable risk, or execution costs eroding returns
- **New**: identified gap; opportunity complements existing book

### Rebalancing timing
- Optimal rebalance window given trend/chop/high-vol regime
- Triggers: time-based vs threshold-based
- Prioritized execution sequence

## Required outputs
1. **Position action table** — Every line item: increase/hold/reduce/exit with magnitude and priority, table format
2. **New opportunity list** — 1–3 additions from gaps found in the triad review, with rationale
3. **Rebalance playbook** — Time window, order of operations, caveats
4. **Risk budget** — Updated per-name risk ceilings from risk findings; keep aggregate risk controlled
5. **Next review focus** — Given this period’s findings, 3–5 KPIs or names to track next {review_period}

Use load_skill("asset-allocation") for allocation decisions, load_skill("risk-analysis") for risk budgeting.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['asset-allocation', 'risk-analysis'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_attribution", "type": "REASON", "agent": "attribution_analyst"},
        {"name": "task_risk", "type": "REASON", "agent": "risk_inspector"},
        {"name": "task_execution", "type": "REASON", "agent": "execution_analyst"},
        {"name": "task_cio_decision", "type": "REASON", "agent": "chief_investment_officer"},
    ],
    "variables": [{'name': 'portfolio', 'description': 'Portfolio name or description (e.g., value-growth blend, CSI 300 enhanced)', 'required': True}, {'name': 'review_period', 'description': 'Review cadence (monthly / quarterly)', 'required': True}, {'name': 'goal', 'description': 'Focus of this review (e.g., assess Q1 performance, diagnose recent NAV drawdown)', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_attribution(state: State) -> dict:
    """REASON: Performance Attribution Analyst"""
    # Build context from state
    context = {
        "portfolio": state.get("portfolio", ""),
        "review_period": state.get("review_period", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("attribution_analyst", context)
    log_event("task_attribution", f"Completed: {len(result.summary)} chars")
    return {"task_attribution_summary": result.summary}


async def task_risk(state: State) -> dict:
    """REASON: Risk Inspector"""
    # Build context from state
    context = {
        "portfolio": state.get("portfolio", ""),
        "review_period": state.get("review_period", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("risk_inspector", context)
    log_event("task_risk", f"Completed: {len(result.summary)} chars")
    return {"task_risk_summary": result.summary}


async def task_execution(state: State) -> dict:
    """REASON: Execution Quality Analyst"""
    # Build context from state
    context = {
        "portfolio": state.get("portfolio", ""),
        "review_period": state.get("review_period", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("execution_analyst", context)
    log_event("task_execution", f"Completed: {len(result.summary)} chars")
    return {"task_execution_summary": result.summary}


async def task_cio_decision(state: State) -> dict:
    """REASON: Chief Investment Officer"""
    # Build context from state
    context = {
        "portfolio": state.get("portfolio", ""),
        "review_period": state.get("review_period", ""),
        "goal": state.get("goal", ""),
        # Upstream summaries
        "attribution_report": state.get("task_attribution_summary", ""),
        "risk_report": state.get("task_risk_summary", ""),
        "execution_report": state.get("task_execution_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_attribution_summary"):
        upstream_parts.append("## Attribution Report\n" + state["task_attribution_summary"])
    if state.get("task_risk_summary"):
        upstream_parts.append("## Risk Report\n" + state["task_risk_summary"])
    if state.get("task_execution_summary"):
        upstream_parts.append("## Execution Report\n" + state["task_execution_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("chief_investment_officer", context)
    log_event("task_cio_decision", f"Completed: {len(result.summary)} chars")
    return {"task_cio_decision_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_attribution", task_attribution)
    g.add_node("task_risk", task_risk)
    g.add_node("task_execution", task_execution)
    g.add_node("task_cio_decision", task_cio_decision)

    g.set_entry_point("task_attribution")
    g.add_edge("task_attribution", "task_cio_decision")
    g.add_edge("task_risk", "task_cio_decision")
    g.add_edge("task_execution", "task_cio_decision")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_attribution", "task_execution")
    g.add_edge("task_attribution", "task_risk")
    g.add_edge("task_cio_decision", END)

    return g.compile()
