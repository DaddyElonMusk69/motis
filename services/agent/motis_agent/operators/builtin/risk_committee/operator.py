"""
Risk Committee
==============

Drawdown, tail risk, and market regime reviews run in parallel; head of risk signs off.

Auto-generated from vibe trading preset: risk_committee.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    goal: str  # Audit target (e.g., BTC position risk, CSI 300 strategy risk)
    task_drawdown_summary: str  # Output from drawdown_analyst
    task_tail_summary: str  # Output from tail_risk_analyst
    task_regime_summary: str  # Output from regime_detector
    task_aggregate_summary: str  # Output from aggregator
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Risk Committee",
    "version": 1,
    "type": "research",
    "description": """Drawdown, tail risk, and market regime reviews run in parallel; head of risk signs off.""",
    "agents": {
        "drawdown_analyst": {
            "role": "Drawdown Analyst",
            "system_prompt": """You are a senior drawdown analyst, skilled in historical drawdown characterization and early warning.

## Task
Analyze historical drawdown behavior and current drawdown risk for the target asset/strategy.

{upstream_context}

## Required outputs
1. **Maximum drawdown statistics** — Top 5 historical drawdown events (magnitude, start/end dates, duration)
2. **Drawdown frequency distribution** — Count of drawdowns by magnitude bucket
3. **Recovery analysis** — Average and maximum time to recover to prior peak
4. **Current drawdown state** — Whether in a drawdown now; distance from last high
5. **Drawdown alert** — Estimated drawdown probability based on volatility and trend

Use load_skill for data access and volatility methods.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['volatility'],
            "max_iterations": 50,
            "model_name": None,
        },
        "tail_risk_analyst": {
            "role": "Tail Risk Analyst",
            "system_prompt": """You are a senior tail-risk analyst, skilled in extreme-scenario assessment and stress testing.

## Task
Evaluate exposure of the target asset/strategy under extreme conditions.

{upstream_context}

## Required outputs
1. **VaR estimates** — 95%/99%/99.9% VaR via parametric + historical simulation
2. **CVaR (ES)** — Conditional tail expectation / expected shortfall
3. **Stress tests** — At least three historical crisis scenarios with simulated loss
4. **Tail event probability** — Extreme-value (GEV/GPD style) probability framing where appropriate
5. **Protection ideas** — Methods to hedge tail risk

Use load_skill for vol analytics and statistical methods.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['volatility'],
            "max_iterations": 50,
            "model_name": None,
        },
        "regime_detector": {
            "role": "Market Regime Analyst",
            "system_prompt": """You are a senior market-regime analyst, skilled in identifying regimes and regime-shift signals.

## Task
Determine the current regime for the market of the target asset.

{upstream_context}

## Required outputs
1. **Current regime** — Bull / bear / chop with confidence
2. **Regime characteristics** — Vol level, trend strength, momentum indicators
3. **Transition signals** — Leading indicators of regime change and current readings
4. **Historical analogs** — 2–3 past periods most similar to today
5. **Forward look** — 1–3 month path probabilities under a regime framework

Use load_skill for technical and volatility methods.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['volatility', 'technical-basic'],
            "max_iterations": 50,
            "model_name": None,
        },
        "aggregator": {
            "role": "Head of Risk",
            "system_prompt": """You are a senior head of risk, skilled at integrating multi-dimensional risk analyses into firm recommendations.

## Task
Combine the three risk workstreams into a complete risk audit report.

{upstream_context}

## Required outputs
Deliver a full Markdown risk report with this structure:
1. **Risk overview** — One-line summary of risk level (low/medium/high/extreme)
2. **Drawdown risk** — Integrate drawdown analyst conclusions
3. **Tail risk** — Integrate tail-risk analyst conclusions
4. **Market regime** — Integrate regime analyst conclusions
5. **Integrated assessment** — Cross-check conclusions across the three dimensions
6. **Action items** — Clear guidance on sizing, stops, and hedges

Conclusions must be data-grounded and actionable.""",
            "tools": ['bash', 'read_file', 'write_file'],
            "skills": [],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_drawdown", "type": "REASON", "agent": "drawdown_analyst"},
        {"name": "task_tail", "type": "REASON", "agent": "tail_risk_analyst"},
        {"name": "task_regime", "type": "REASON", "agent": "regime_detector"},
        {"name": "task_aggregate", "type": "REASON", "agent": "aggregator"},
    ],
    "variables": [{'name': 'goal', 'description': 'Audit target (e.g., BTC position risk, CSI 300 strategy risk)', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_drawdown(state: State) -> dict:
    """REASON: Drawdown Analyst"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("drawdown_analyst", context)
    log_event("task_drawdown", f"Completed: {len(result.summary)} chars")
    return {"task_drawdown_summary": result.summary}


async def task_tail(state: State) -> dict:
    """REASON: Tail Risk Analyst"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("tail_risk_analyst", context)
    log_event("task_tail", f"Completed: {len(result.summary)} chars")
    return {"task_tail_summary": result.summary}


async def task_regime(state: State) -> dict:
    """REASON: Market Regime Analyst"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("regime_detector", context)
    log_event("task_regime", f"Completed: {len(result.summary)} chars")
    return {"task_regime_summary": result.summary}


async def task_aggregate(state: State) -> dict:
    """REASON: Head of Risk"""
    # Build context from state
    context = {
        "goal": state.get("goal", ""),
        # Upstream summaries
        "drawdown": state.get("task_drawdown_summary", ""),
        "tail_risk": state.get("task_tail_summary", ""),
        "regime": state.get("task_regime_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_drawdown_summary"):
        upstream_parts.append("## Drawdown\n" + state["task_drawdown_summary"])
    if state.get("task_tail_summary"):
        upstream_parts.append("## Tail Risk\n" + state["task_tail_summary"])
    if state.get("task_regime_summary"):
        upstream_parts.append("## Regime\n" + state["task_regime_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("aggregator", context)
    log_event("task_aggregate", f"Completed: {len(result.summary)} chars")
    return {"task_aggregate_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_drawdown", task_drawdown)
    g.add_node("task_tail", task_tail)
    g.add_node("task_regime", task_regime)
    g.add_node("task_aggregate", task_aggregate)

    g.set_entry_point("task_drawdown")
    g.add_edge("task_drawdown", "task_aggregate")
    g.add_edge("task_tail", "task_aggregate")
    g.add_edge("task_regime", "task_aggregate")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_drawdown", "task_regime")
    g.add_edge("task_drawdown", "task_tail")
    g.add_edge("task_aggregate", END)

    return g.compile()
