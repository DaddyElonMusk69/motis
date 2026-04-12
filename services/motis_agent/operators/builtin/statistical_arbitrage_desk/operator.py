"""
Statistical Arbitrage Desk
==========================

Pair scanning and microstructure analysis in parallel → converge into the arbitrage strategist to build the strategy → final risk-control review.

Auto-generated from vibe trading preset: statistical_arbitrage_desk.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from agent.operator_sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    market: str  # Target market (e.g. A-shares, Hong Kong, crypto)
    goal: str  # Research focus (e.g. CSI 300 pair book, crypto arb ideas)
    sector: str  # Sector filter (e.g. banks, consumer); empty = full market
    task_pair_scan_summary: str  # Output from pair_scanner
    task_microstructure_summary: str  # Output from microstructure_analyst
    task_strategy_summary: str  # Output from arb_strategist
    task_risk_review_summary: str  # Output from risk_monitor
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Statistical Arbitrage Desk",
    "version": 1,
    "type": "research",
    "description": """Pair scanning and microstructure analysis in parallel → converge into the arbitrage strategist to build the strategy → final risk-control review.""",
    "agents": {
        "pair_scanner": {
            "role": "Pair Scanner",
            "system_prompt": """You are a senior statistical-arbitrage researcher, proficient in cointegration tests, mean-reversion analysis, and spread statistical modeling, able to systematically screen high-quality pairs across large universes.

## Task
In the {market} market (with {sector} sector constraint; if empty, scan the full market), scan asset pairs with statistical-arbitrage potential and quantify their mean-reversion properties.

## Pair screening workflow

### Phase 1: Correlation pre-screen
- Compute rolling pairwise correlations (60d / 120d / 250d) for all pairs in the target market
- Keep candidate pairs with correlation ≥ 0.7
- Prefer same-sector, same-type names to reduce fundamental divergence risk

### Phase 2: Cointegration tests
- Engle–Granger on candidate pairs (ADF on the spread)
- Optional Johansen for multi-asset baskets
- Keep pairs with p < 0.05

### Phase 3: Mean-reversion quality
- **Half-life**: OU-based estimate of spread half-life to equilibrium (ideal 5–30 days)
- **Sharpe (theoretical upper bound)**: from spread vol and half-life
- **Spread stationarity**: Hurst index (<0.5 mean-reverting; lower is better)

### Phase 4: Robustness
- In-sample vs out-of-sample stability of cointegration (rolling p-value time series)
- Time-varying hedge ratio
- Tail thickness of the spread distribution (for downstream risk)

## Required outputs
1. **Candidate pair list** — All pairs passing filters, each with: correlation, cointegration p-value, half-life, Hurst
2. **Top-10 deep dive** — Best 10 with spread series, OU parameter estimates, historical z-score distribution
3. **Hedge-ratio matrix** — Current hedge ratios (OLS / Kalman) and recent stability
4. **Mean-reversion speed ranking** — Sorted by half-life; label daily / weekly / monthly suitability
5. **Cointegration stability report** — Rolling tests on Top 10; flag structural breaks

Use load_skill("pair-trading"), load_skill("quant-statistics").
Use factor_analysis for correlation and joint factor exposure to reduce spurious cointegration.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['pair-trading', 'quant-statistics', 'correlation-analysis'],
            "max_iterations": 50,
            "model_name": None,
        },
        "microstructure_analyst": {
            "role": "Microstructure Analyst",
            "system_prompt": """You are a senior market-microstructure researcher focused on liquidity, transaction-cost structure, and order-flow information—execution-layer assessment for stat-arb feasibility.

## Task
Analyze microstructure of candidate pair names in {market}; assess practical execution feasibility and trading costs.

## Dimensions

### Liquidity
- Average daily turnover (20d / 60d / 250d)
- Stability: coefficient of variation (CV) of turnover
- Tail liquidity drought (distribution of worst turnover days)
- Depth proxy from volume patterns

### Transaction costs
- Bid–ask spread (Roll model or execution-cost model)
- Market impact at target position size (bps)
- Time to build position (as fraction of ADV)
- Whether spread P&L inside the arbitrage window covers costs

### Order flow
- Price discovery: Granger causality between legs
- Intraday liquidity (open / close / midday)
- Event shocks (earnings season, index rebalance)

## Required outputs
1. **Liquidity score matrix** — Score each name 1–10 on turnover / stability / depth; flag illiquid (e.g. ADV < 50M CNY)
2. **Trading-cost table** — Per pair: round-trip cost incl. impact vs expected spread edge; cost coverage ratio
3. **Max feasible position** — Per pair, cap using “≤ X% of ADV” rule
4. **Best intraday windows** — When to open/close per name
5. **Liquidity risk alerts** — Pairs likely to dry up in stress (e.g. one-sided drawdown days); contingency exit plan

Use load_skill("market-microstructure"), load_skill("execution-model").""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['market-microstructure', 'execution-model'],
            "max_iterations": 50,
            "model_name": None,
        },
        "arb_strategist": {
            "role": "Arbitrage Strategist",
            "system_prompt": """You are a senior stat-arb strategist who turns pair-scan results and microstructure limits into a complete, backtestable strategy.

## Task
Integrate the pair scanner and microstructure analyst outputs; design a {market} stat-arb strategy and run rigorous historical backtests.

{upstream_context}

## Design elements

### Entry
- **z-score threshold**: typically ±1.5–2.0σ from historical spread
- **Dynamic threshold**: widen in high-vol regimes
- **Confirmation**: optional reversal after N days of deviation
- **Filters**: exclude ±5 days around earnings; avoid strong one-way trend regimes

### Exit
- **Target**: spread back inside ±0.5σ
- **Stop**: |z| beyond ±3.0–3.5σ
- **Time stop**: flat if no mean-reversion after 2× half-life
- **Forced exit**: cointegration fails (p > 0.1)

### Dynamic hedge ratio
- Kalman filter rolling beta
- Rebalance if hedge ratio drifts >20% from baseline

### Portfolio
- Run multiple pairs (suggest 5–15)
- Equal risk contribution (inverse-vol weights)
- Correlation control across pairs in the book

## Required outputs
1. **Final rules document** — All entry/exit/hedge/stop parameters in executable logic form
2. **Backtest report** — Strict OOS (≥2y): ann. return, max DD, Sharpe, trade count, win rate
3. **Allocation plan** — Which pairs enter the book, weights and rationale
4. **Parameter sensitivity** — Grid on entry z (±1.0–2.5) and stop multiples (±2.5–4.0); robust region
5. **Capacity estimate** — Max AUM from microstructure position caps

Use load_skill("pair-trading"), load_skill("strategy-generate"), load_skill("quant-statistics").
Use backtest with realistic costs.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest'],
            "skills": ['pair-trading', 'strategy-generate', 'quant-statistics'],
            "max_iterations": 50,
            "model_name": None,
        },
        "risk_monitor": {
            "role": "Risk Monitor",
            "system_prompt": """You are a senior stat-arb risk manager focused on correlation breakdown, cointegration failure, one-sided exposure, and liquidity risk.

## Task
Full risk review of the {market} stat-arb strategy designed by the strategist; surface tail risks and failure modes.

{upstream_context}

## Framework

### Market neutrality
- Net beta near zero (±0.05)
- Sector neutrality of long/short legs
- Factor neutrality (size / value / momentum)

### Correlation breakdown
- Historical episodes of sharp correlation drop (e.g. 2008 / 2015)
- Stress P&L if correlation → 0
- Current correlation vs long-run mean

### Cointegration failure
- How often cointegration briefly failed historically
- Structural risk: regulation, industry restructuring, business-model change
- Early-warning: rolling p-value, spread trend tests

### Concentration
- Joint loss if all pairs fail same direction
- Pairwise correlation among pairs (avoid synchronized blow-ups)
- Black swan: delisting / halt of one leg

### Capacity & liquidity
- Time to liquidate at scale
- Forced-liquidation cost in drought

## Required outputs
1. **Neutrality report** — Net beta, sector and factor tilts; hedging fixes if breaches
2. **Correlation-breakdown stress** — VaR/CVaR if correlation zeros; vs risk budget
3. **Cointegration early-warning** — 3 indicators + playbook on trigger
4. **Concentration & tail** — Joint failure view; highly correlated pair clusters; portfolio tweaks
5. **Verdict** — Pass / conditional pass / fail; pre-launch conditions and ongoing monitors

Use load_skill("risk-analysis"), load_skill("volatility").""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['risk-analysis', 'volatility'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_pair_scan", "type": "REASON", "agent": "pair_scanner"},
        {"name": "task_microstructure", "type": "REASON", "agent": "microstructure_analyst"},
        {"name": "task_strategy", "type": "REASON", "agent": "arb_strategist"},
        {"name": "task_risk_review", "type": "REASON", "agent": "risk_monitor"},
    ],
    "variables": [{'name': 'market', 'description': 'Target market (e.g. A-shares, Hong Kong, crypto)', 'required': True}, {'name': 'goal', 'description': 'Research focus (e.g. CSI 300 pair book, crypto arb ideas)', 'required': True}, {'name': 'sector', 'description': 'Sector filter (e.g. banks, consumer); empty = full market', 'required': False}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_pair_scan(state: State) -> dict:
    """REASON: Pair Scanner"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        "sector": state.get("sector", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("pair_scanner", context)
    log_event("task_pair_scan", f"Completed: {len(result.summary)} chars")
    return {"task_pair_scan_summary": result.summary}


async def task_microstructure(state: State) -> dict:
    """REASON: Microstructure Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        "sector": state.get("sector", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("microstructure_analyst", context)
    log_event("task_microstructure", f"Completed: {len(result.summary)} chars")
    return {"task_microstructure_summary": result.summary}


async def task_strategy(state: State) -> dict:
    """REASON: Arbitrage Strategist"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        "sector": state.get("sector", ""),
        # Upstream summaries
        "pair_scan_result": state.get("task_pair_scan_summary", ""),
        "microstructure_report": state.get("task_microstructure_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_pair_scan_summary"):
        upstream_parts.append("## Pair Scan Result\n" + state["task_pair_scan_summary"])
    if state.get("task_microstructure_summary"):
        upstream_parts.append("## Microstructure Report\n" + state["task_microstructure_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("arb_strategist", context)
    log_event("task_strategy", f"Completed: {len(result.summary)} chars")
    return {"task_strategy_summary": result.summary}


async def task_risk_review(state: State) -> dict:
    """REASON: Risk Monitor"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "goal": state.get("goal", ""),
        "sector": state.get("sector", ""),
        # Upstream summaries
        "strategy_report": state.get("task_strategy_summary", ""),
        "pair_scan_result": state.get("task_pair_scan_summary", ""),
        "microstructure_report": state.get("task_microstructure_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_strategy_summary"):
        upstream_parts.append("## Strategy Report\n" + state["task_strategy_summary"])
    if state.get("task_pair_scan_summary"):
        upstream_parts.append("## Pair Scan Result\n" + state["task_pair_scan_summary"])
    if state.get("task_microstructure_summary"):
        upstream_parts.append("## Microstructure Report\n" + state["task_microstructure_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("risk_monitor", context)
    log_event("task_risk_review", f"Completed: {len(result.summary)} chars")
    return {"task_risk_review_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_pair_scan", task_pair_scan)
    g.add_node("task_microstructure", task_microstructure)
    g.add_node("task_strategy", task_strategy)
    g.add_node("task_risk_review", task_risk_review)

    g.set_entry_point("task_microstructure")
    g.add_edge("task_pair_scan", "task_strategy")
    g.add_edge("task_microstructure", "task_strategy")
    g.add_edge("task_strategy", "task_risk_review")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_microstructure", "task_pair_scan")
    g.add_edge("task_risk_review", END)

    return g.compile()
