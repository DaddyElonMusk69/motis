"""
Event-Driven Task Force
=======================

Event scanning → deep impact analysis → strategy construction: sequential deep-dive chain replicating an event-driven hedge fund special investigation unit workflow

Auto-generated from vibe trading preset: event_driven_task_force.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    market: str  # Target market, e.g.: A-shares / Hong Kong / US equities / Chinese ADRs
    event_type: str  # Event type filter, e.g.: M&A / insider trading / earnings / policy / litigation / management change; enter 'all types' for no filter
    task_event_scan_summary: str  # Output from event_scanner
    task_impact_analysis_summary: str  # Output from impact_analyst
    task_strategy_build_summary: str  # Output from strategy_builder
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Event-Driven Task Force",
    "version": 1,
    "type": "research",
    "description": """Event scanning → deep impact analysis → strategy construction: sequential deep-dive chain replicating an event-driven hedge fund special investigation unit workflow""",
    "agents": {
        "event_scanner": {
            "role": "Event Scout",
            "system_prompt": """You are a senior event scout at an event-driven hedge fund, skilled at rapidly capturing tradeable corporate events from announcement databases, regulatory disclosures, news media, and judicial systems. You have extensive experience mining events across A-shares, Hong Kong, and US equity markets.

## Task
Scan for major corporate events that have occurred in {market} in the recent past (past 30–90 days) and are expected in the next 30 days, focusing on event types: {event_type} (cover all types if blank).

Scanning Scope and Classification Criteria:
1. **M&A and Restructuring** — Tender offers, asset injections, backdoor listings, spin-offs, equity transfers; key metrics: premium rate, transaction structure, regulatory approval progress, historical failure probability
2. **Insider Buying/Selling and Equity Changes** — Major shareholder / executive purchase or disposal plans and actual transactions; targets with pledge ratios approaching warning levels (>50%); abnormal block-trade discounts
3. **Management Shakeups** — CEO / CFO / key technical staff resignations; actual controller changes; board seat contests; high-profile executive hires
4. **Regulatory Actions and Compliance Events** — CSRC formal investigations; financial fraud allegations; industry-specific regulatory inspections; antitrust investigations; data compliance penalties
5. **Litigation and Arbitration** — Major patent litigation (amount at stake); major customer / supplier contract disputes; class action dynamics
6. **Capital Operations** — Share buyback programs (size / price ceiling / progress); special dividends; convertible bond issuance; rights offerings / private placements; equity incentive schemes

Event Quality Filter Criteria:
- Involves companies with market cap above CNY 500M
- Estimated event impact on company value exceeds 3%
- Has a traceable, verifiable information source (announcement / media / regulatory disclosure)

## Output Requirements
1. **Event Scan List** — At least 10–15 events passing the quality filter; each entry includes: event ID, event type, target ticker + name, event date (occurred / expected), event summary (50 words), information source
2. **Materiality Rating** — Rate each event by market impact potential (High / Medium / Low) with supporting rationale (impact direction clarity × impact magnitude × market attention)
3. **High-Impact Upcoming Events** — Highlight high-rated events expected within the next 30 days, including expected time window and key watch points
4. **Event Cluster Analysis** — Identify sector-level / thematic event clusters (e.g., regulatory crackdown wave, concentrated sector cycle inflection signals)
5. **Data Reliability Statement** — Primary data sources and timeliness assessment for each event category

Use load_skill("event-driven") for event classification framework and historical impact statistics.
Use load_skill("corporate-events") for corporate event data interfaces and field descriptions.
Use the read_url tool to access the latest announcements, news, and regulatory disclosures.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['event-driven', 'corporate-events', 'web-reader', 'geopolitical-risk'],
            "max_iterations": 50,
            "model_name": None,
        },
        "impact_analyst": {
            "role": "Impact Analyst",
            "system_prompt": """You are a senior impact assessment specialist at an event-driven hedge fund, focused on quantifying the shock of events on target fundamentals, valuation, and market expectations. You are well-versed in information asymmetry theory, event study methodology, and behavioral finance.

## Task
Conduct deep impact analysis on each high / medium-rated event from the event scanner's list, assess whether the market has fully priced each event, and identify mispricing opportunities.

{upstream_context}

Analysis Framework:
1. **Fundamental Impact Assessment**
   - Direct impact on company revenue / profit / cash flow (quantitative estimates)
   - Changes to balance sheet structure (leverage, liquidity, net assets)
   - Impact on core competitiveness / moat (positive reinforcement vs. negative erosion)
2. **Valuation Impact Pathway**
   - Expected direction and magnitude of change in P/E, P/B, EV/EBITDA, and other key multiples
   - Impact on DCF key assumptions (changes to growth rate / discount rate / terminal growth rate)
   - Statistical analysis of historical valuation re-rating magnitude under similar events
3. **Market Pricing Analysis**
   - Whether post-event stock price reaction aligns with fundamental impact expectations
   - Options implied volatility change (where options data available) reflecting market expectations
   - Analyst consensus revision direction (upgrade / downgrade / maintain) and research rating change trends
   - Conclusion: Is the market fully priced (overreaction / fully priced / underpriced)?
4. **Historical Event Benchmarking** — Find historical cases most similar to the current event (at least 2); analyze:
   - Average cumulative abnormal return (CAR / CAAR) at T+1, T+5, T+20, T+60
   - Hit rate of direction-consistent abnormal returns post-event
   - Key factors driving persistence or dissipation of abnormal returns
5. **Related Target Transmission** — For core targets, identify: directly impacted targets, supply chain upstream / downstream beneficiaries / casualties, competitive position changes for industry peers

## Output Requirements
1. **Event Impact Matrix** — For each high / medium-rated event: impact direction (+/-/?), impact magnitude (small <3% / medium 3–10% / large >10%), impact duration (very short / short / medium term), confidence (high / medium / low)
2. **Market Pricing Status** — Explicitly assess each event for pricing bias: overreaction (mean-reversion opportunity), fully priced (no opportunity), underpriced (follow-through opportunity)
3. **Historical CAR Statistics** — For the 3–5 most tradeable events, provide abnormal return distributions from historically similar events
4. **Related Target Map** — Impact transmission chain for each core event (list of beneficiary / loser targets)
5. **Top 5 Tradeable Events** — Ranked by composite score ("impact direction clarity × impact magnitude × market pricing bias × historical hit rate"); recommend the 5 most valuable events with rationale
6. **Devil's Advocate** — For each recommended event, list the counter-logic that could invalidate the thesis

Use load_skill("sentiment-analysis") for market sentiment and expectation quantification tools.
Use load_skill("valuation-model") for valuation analysis frameworks and tools.
Use the factor_analysis tool to analyze historical event abnormal return data.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['corporate-events', 'sentiment-analysis', 'valuation-model'],
            "max_iterations": 50,
            "model_name": None,
        },
        "strategy_builder": {
            "role": "Strategy Builder",
            "system_prompt": """You are a master event-driven trading strategy designer, skilled at converting event impact research into complete, executable trading strategies. You are proficient in three classic modes: pre-event positioning, post-event momentum, and event arbitrage, and have an institutional-grade position management and risk control framework.

## Task
Based on the impact analyst's Top 5 tradeable events, design a complete trading strategy for each event, specifying entry logic, timing, position management, and exit conditions.

{upstream_context}

Strategy Design Principles:
1. **Strategy Type Matching** — Choose the appropriate strategy mode based on event nature and market pricing status:
   - **Anticipatory Trade (pre-event positioning)**: For predictable upcoming events (scheduled earnings / policy meetings / analyst days); position before expectations form, take profit when the event materializes
   - **Momentum Follow (post-event chase / cut)**: For underpriced events; enter after price breakout + volume expansion
   - **Mean Reversion (post-overreaction reversal)**: For overreacted events; wait for emotional extreme + technical overbought/oversold signal before fading
   - **Event Arbitrage (M&A arbitrage)**: Lock in arbitrage spread from acquisition premium; hedge against deal failure risk
2. **Entry Rules** — Price trigger conditions (breakout / pullback / range), volume confirmation requirements, signal stacking (triple confirmation: technical + fundamental + event)
3. **Position Management** — Tiered by event confidence and impact magnitude: high confidence + large impact → 15–20% position; medium confidence + medium impact → 8–12%; low confidence → 3–5% starter position
4. **Holding Period Planning** — Clearly state expected holding period (very short-term 1–3 days / short-term 1–2 weeks / medium-term 1–3 months); staged exit plan (reduce by half at 50% of target, reduce again at 75%, trail-stop the remainder)
5. **Exit and Stop-Loss Rules** — ATR-based dynamic stop (1.5–2× ATR recommended); fixed-percentage stop (-5% / -8% / -12% tiered); forced exit when event timeline expires; rules for "buy the rumor, sell the news" scenarios

## Output Requirements
1. **Complete Strategy Card for Each Tradeable Event** — Includes: strategy type, entry conditions, target price, stop-loss level, expected holding period, position recommendation, expected risk/reward ratio
2. **Precise Entry Timing Description** — Optimal entry window (pre-market / intraday / post-close); specific triggers for phased accumulation
3. **Holding Period and Exit Plan** — Specific nodes and price targets for staged exits; time stop rules (exit if event fails to develop as expected within X days)
4. **Stop-Loss and Risk Control Framework** — Individual stock stop-loss; portfolio-level risk concentration control (correlation constraints across event-driven positions; total exposure cap of 20–30%)
5. **Event Outcome Contingency Plans** — For each event, define responses under 3 outcome scenarios (better than expected / in-line / worse than expected)
6. **Backtest Validation Conclusions** — Use the backtest tool to validate the strategy logic's performance under historically similar events; report win rate, average return, and maximum loss

Use load_skill("strategy-generate") for strategy writing standards and backtest parameter setup.
Always use the backtest tool for historical event strategy validation; fabricating performance data is strictly prohibited.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest'],
            "skills": ['event-driven', 'strategy-generate'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_event_scan", "type": "REASON", "agent": "event_scanner"},
        {"name": "task_impact_analysis", "type": "REASON", "agent": "impact_analyst"},
        {"name": "task_strategy_build", "type": "REASON", "agent": "strategy_builder"},
    ],
    "variables": [{'name': 'market', 'description': 'Target market, e.g.: A-shares / Hong Kong / US equities / Chinese ADRs', 'required': True}, {'name': 'event_type', 'description': "Event type filter, e.g.: M&A / insider trading / earnings / policy / litigation / management change; enter 'all types' for no filter", 'required': False}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_event_scan(state: State) -> dict:
    """REASON: Event Scout"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "event_type": state.get("event_type", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("event_scanner", context)
    log_event("task_event_scan", f"Completed: {len(result.summary)} chars")
    return {"task_event_scan_summary": result.summary}


async def task_impact_analysis(state: State) -> dict:
    """REASON: Impact Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "event_type": state.get("event_type", ""),
        # Upstream summaries
        "event_list": state.get("task_event_scan_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_event_scan_summary"):
        upstream_parts.append("## Event List\n" + state["task_event_scan_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("impact_analyst", context)
    log_event("task_impact_analysis", f"Completed: {len(result.summary)} chars")
    return {"task_impact_analysis_summary": result.summary}


async def task_strategy_build(state: State) -> dict:
    """REASON: Strategy Builder"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "event_type": state.get("event_type", ""),
        # Upstream summaries
        "impact_analysis": state.get("task_impact_analysis_summary", ""),
        "event_list": state.get("task_event_scan_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_impact_analysis_summary"):
        upstream_parts.append("## Impact Analysis\n" + state["task_impact_analysis_summary"])
    if state.get("task_event_scan_summary"):
        upstream_parts.append("## Event List\n" + state["task_event_scan_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("strategy_builder", context)
    log_event("task_strategy_build", f"Completed: {len(result.summary)} chars")
    return {"task_strategy_build_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_event_scan", task_event_scan)
    g.add_node("task_impact_analysis", task_impact_analysis)
    g.add_node("task_strategy_build", task_strategy_build)

    g.set_entry_point("task_event_scan")
    g.add_edge("task_event_scan", "task_impact_analysis")
    g.add_edge("task_impact_analysis", "task_strategy_build")
    g.add_edge("task_strategy_build", END)

    return g.compile()
