"""
Equity Research Team
====================

Macro → sector → stock three-tier deep research → research editor consolidates into a complete report

Auto-generated from vibe trading preset: equity_research_team.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    market: str  # Target market (e.g.: A-shares, Hong Kong, Crypto)
    goal: str  # Research focus (e.g.: Q2 2026 outlook, opportunities in the new energy sector)
    task_macro_summary: str  # Output from macro_analyst
    task_sector_summary: str  # Output from sector_analyst
    task_stock_summary: str  # Output from stock_picker
    task_aggregate_summary: str  # Output from aggregator
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Equity Research Team",
    "version": 1,
    "type": "research",
    "description": """Macro → sector → stock three-tier deep research → research editor consolidates into a complete report""",
    "agents": {
        "macro_analyst": {
            "role": "Macro Analyst",
            "system_prompt": """You are a senior macroeconomic analyst with expertise in analyzing the global macro environment, central bank monetary policy, and geopolitical risks.

## Task
Analyze the current macroeconomic environment and its impact on the {market} market.

{upstream_context}

## Output Requirements
Please produce a structured analysis report with the following sections:
1. **Macro Overview** — Interpretation of core indicators: GDP, CPI, PMI, etc.
2. **Monetary Policy and Liquidity** — Key signals from interest rates, M2, credit, etc.
3. **Global Market Linkages** — Spillover effects of Fed / ECB policy
4. **Risk Factors** — Identify 3–5 major macro risk points
5. **Conclusion for {market}** — Summarize the bullish / bearish / neutral rationale

Use load_skill to access data query methods; prioritize using tools to obtain the latest data to support the analysis.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['tushare', 'okx-market', 'yfinance', 'web-reader', 'global-macro'],
            "max_iterations": 50,
            "model_name": None,
        },
        "sector_analyst": {
            "role": "Sector Analyst",
            "system_prompt": """You are a senior sector analyst with expertise in sector prosperity assessment, industry chain analysis, and competitive landscape research.

## Task
Based on the macroeconomic analysis, identify the most promising sectors in {market}.

{upstream_context}

## Output Requirements
Please produce a structured analysis report with the following sections:
1. **Sector Prosperity Ranking** — Top 5 sectors with scoring rationale
2. **Core Growth Drivers** — The growth logic for each recommended sector
3. **Industry Chain Analysis** — Degree of benefit across upstream, midstream, and downstream
4. **Competitive Landscape** — Concentration, entry barriers, leading companies
5. **Recommended Sectors and Rationale** — Explicitly recommend 2–3 sectors with suggested allocation weights

Use the factor_analysis tool for factor-based analysis to support judgments.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['tushare', 'yfinance', 'fundamental-filter', 'multi-factor', 'us-etf-flow', 'sector-rotation'],
            "max_iterations": 50,
            "model_name": None,
        },
        "stock_picker": {
            "role": "Stock Analyst",
            "system_prompt": """You are a senior stock analyst combining technical and fundamental analysis for stock selection.

## Task
Screen specific investment targets from the recommended sectors and conduct a combined technical + fundamental assessment.

{upstream_context}

## Output Requirements
Please produce a structured analysis report with the following sections:
1. **Recommended Target List** — Each target with ticker, name, and sector
2. **Fundamental Assessment** — Core metrics: P/E, P/B, ROE, revenue growth, etc.
3. **Technical Signals** — Trend, support/resistance levels, price-volume dynamics
4. **Entry Logic** — Buy trigger conditions for each target
5. **Risk Disclosure** — Primary risks for each target

Always use load_skill("strategy-generate") for strategy writing standards.
Use the backtest tool to validate the historical performance of stock selection logic.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest', 'factor_analysis'],
            "skills": ['tushare', 'yfinance', 'strategy-generate', 'technical-basic', 'multi-factor', 'earnings-revision'],
            "max_iterations": 50,
            "model_name": None,
        },
        "aggregator": {
            "role": "Research Report Editor",
            "system_prompt": """You are a senior research report editor skilled at integrating multi-dimensional analysis into a logically rigorous investment research report.

## Task
Synthesize all analysts' research outputs and produce a complete, professional investment research report.

{upstream_context}

## Output Requirements
Please produce a complete Markdown-format research report with the following structure:
1. **Executive Summary** — Key investment points in under 200 words
2. **Macro Environment** — Integrate macro analyst conclusions
3. **Sector Allocation** — Integrate sector analyst recommendations
4. **Stock Recommendations** — Integrate stock analyst selections
5. **Risk Disclosures** — Aggregate all risk factors
6. **Action Recommendations** — Provide clear position and timing guidance

Ensure the report is internally consistent, data is traceable, and conclusions are logically supported.""",
            "tools": ['bash', 'read_file', 'write_file'],
            "skills": ['report-generate'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_macro", "type": "REASON", "agent": "macro_analyst"},
        {"name": "task_sector", "type": "REASON", "agent": "sector_analyst"},
        {"name": "task_stock", "type": "REASON", "agent": "stock_picker"},
        {"name": "task_aggregate", "type": "REASON", "agent": "aggregator"},
    ],
    "variables": [{'name': 'market', 'description': 'Target market (e.g.: A-shares, Hong Kong, Crypto)', 'required': True}, {'name': 'goal', 'description': 'Research focus (e.g.: Q2 2026 outlook, opportunities in the new energy sector)', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_macro(state: State) -> dict:
    """REASON: Macro Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("macro_analyst", context)
    log_event("task_macro", f"Completed: {len(result.summary)} chars")
    return {"task_macro_summary": result.summary}


async def task_sector(state: State) -> dict:
    """REASON: Sector Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        # Upstream summaries
        "macro_context": state.get("task_macro_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_macro_summary"):
        upstream_parts.append("## Macro Context\n" + state["task_macro_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("sector_analyst", context)
    log_event("task_sector", f"Completed: {len(result.summary)} chars")
    return {"task_sector_summary": result.summary}


async def task_stock(state: State) -> dict:
    """REASON: Stock Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        # Upstream summaries
        "sector_context": state.get("task_sector_summary", ""),
        "macro_context": state.get("task_macro_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_sector_summary"):
        upstream_parts.append("## Sector Context\n" + state["task_sector_summary"])
    if state.get("task_macro_summary"):
        upstream_parts.append("## Macro Context\n" + state["task_macro_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("stock_picker", context)
    log_event("task_stock", f"Completed: {len(result.summary)} chars")
    return {"task_stock_summary": result.summary}


async def task_aggregate(state: State) -> dict:
    """REASON: Research Report Editor"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        # Upstream summaries
        "macro": state.get("task_macro_summary", ""),
        "sector": state.get("task_sector_summary", ""),
        "stock": state.get("task_stock_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_macro_summary"):
        upstream_parts.append("## Macro\n" + state["task_macro_summary"])
    if state.get("task_sector_summary"):
        upstream_parts.append("## Sector\n" + state["task_sector_summary"])
    if state.get("task_stock_summary"):
        upstream_parts.append("## Stock\n" + state["task_stock_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("aggregator", context)
    log_event("task_aggregate", f"Completed: {len(result.summary)} chars")
    return {"task_aggregate_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_macro", task_macro)
    g.add_node("task_sector", task_sector)
    g.add_node("task_stock", task_stock)
    g.add_node("task_aggregate", task_aggregate)

    g.set_entry_point("task_macro")
    g.add_edge("task_macro", "task_sector")
    g.add_edge("task_sector", "task_stock")
    g.add_edge("task_stock", "task_aggregate")
    g.add_edge("task_aggregate", END)

    return g.compile()
