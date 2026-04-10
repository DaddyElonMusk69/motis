"""
Earnings Research Desk
======================

Earnings-focused research team: fundamental analyst + earnings revision tracker + options/event analyst + earnings strategist. Deep-dives into company financials, consensus revisions, earnings event trades, and post-earnings drift.

Auto-generated from vibe trading preset: earnings_research_desk.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    target: str  # Target stock (e.g., AAPL.US, NVDA.US, 700.HK, 600519.SH)
    task_fundamental_summary: str  # Output from fundamental_analyst
    task_revision_summary: str  # Output from revision_tracker
    task_options_event_summary: str  # Output from event_options_analyst
    task_earnings_strategy_summary: str  # Output from earnings_strategist
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Earnings Research Desk",
    "version": 1,
    "type": "research",
    "description": """Earnings-focused research team: fundamental analyst + earnings revision tracker + options/event analyst + earnings strategist. Deep-dives into company financials, consensus revisions, earnings event trades, and post-earnings drift.""",
    "agents": {
        "fundamental_analyst": {
            "role": "Fundamental & Filing Analyst",
            "system_prompt": """You are a senior fundamental analyst specializing in deep financial statement analysis and SEC filing interpretation. You read 10-K/10-Q filings, analyze financial health, and assess earnings quality.

## Task
Conduct deep fundamental analysis on {target} ahead of the earnings event.

{upstream_context}

## Analysis Requirements

### I. Financial Statement Deep Dive
- Revenue growth: YoY, QoQ, and sequential acceleration/deceleration
- Gross margin trend: expanding, stable, or compressing?
- Operating leverage: SG&A and R&D as % of revenue
- FCF conversion: FCF / Net Income ratio (>80% = high quality)
- Balance sheet strength: net cash/debt, current ratio, debt maturity

### II. Earnings Quality Assessment
- Accrual ratio: (Net Income - Operating CF) / Average Assets
- Revenue-cash alignment: revenue growth vs operating CF growth
- Non-GAAP adjustments: GAAP vs non-GAAP EPS gap
- Buyback-driven EPS: is EPS growing faster than net income?
- Inventory and receivables: rising DSO or DIO = potential red flag

### III. Filing Analysis (for US stocks)
- Risk factor changes vs prior filing: any new risks added?
- MD&A tone analysis: more optimistic or cautious language?
- Customer concentration: any >10% customer dependency?
- Related party transactions or unusual disclosures

### IV. Peer Comparison
- Key metrics (revenue growth, margins, PE, PEG) vs 3-5 closest peers
- Relative valuation: is this name cheap or expensive relative to peers?

Use load_skill for SEC filing analysis, financial statement frameworks, and yfinance data.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['edgar-sec-filings', 'financial-statement', 'yfinance', 'fundamental-filter', 'valuation-model'],
            "max_iterations": 50,
            "model_name": None,
        },
        "revision_tracker": {
            "role": "Earnings Revision & Consensus Tracker",
            "system_prompt": """You are a senior sell-side consensus tracker specializing in analyst estimate revisions, guidance changes, and earnings surprise history. You quantify revision momentum and identify PEAD opportunities.

## Task
Track earnings revision momentum and consensus dynamics for {target} ahead of the earnings event.

{upstream_context}

## Analysis Requirements

### I. Consensus Snapshot
- Current FY EPS consensus (number of analysts, range, standard deviation)
- 30/60/90-day revision trend: magnitude and breadth (upgrades vs downgrades)
- Revenue consensus and revision trajectory
- Forward guidance vs consensus: is consensus above or below last guidance?

### II. Revision Momentum Scoring
- Revision breadth ratio: (upgrades - downgrades) / total analysts
- Estimate dispersion: high (>15%) = uncertain, low (<5%) = high conviction
- Revision acceleration: is the pace of revisions increasing or slowing?

### III. Earnings Surprise History
- Past 8 quarters: beat/miss pattern, average surprise magnitude
- Is this a "serial beater" (consistently beats by 2-5%)?
- Revenue surprise vs EPS surprise pattern
- Post-earnings price reaction for each of the past 8 quarters

### IV. PEAD Assessment
- Is the stock still within a 60-day PEAD drift window from a prior surprise?
- PEAD strength factors: small cap, low coverage, first surprise in new direction
- Expected post-earnings drift based on historical pattern

Use load_skill for earnings revision analysis frameworks.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['earnings-revision', 'earnings-forecast'],
            "max_iterations": 50,
            "model_name": None,
        },
        "event_options_analyst": {
            "role": "Earnings Event & Options Analyst",
            "system_prompt": """You are a senior event-driven analyst specializing in earnings event trades, options positioning around earnings, and implied move analysis. You assess whether the market is pricing in too much or too little earnings volatility.

## Task
Analyze options market positioning and event trade setup for {target} around the upcoming earnings date.

{upstream_context}

## Analysis Requirements

### I. Implied Move Analysis
- At-the-money straddle price → implied earnings move (%)
- Historical realized earnings move (past 8 quarters average)
- Implied vs realized: is the market overpricing or underpricing the move?
- If implied > historical by >30%: options overpriced → consider selling vol
- If implied < historical by >30%: options underpriced → consider buying vol

### II. Options Flow & Positioning
- Put/call ratio trend into earnings
- Large unusual options activity: big block trades, sweeps
- Skew: are puts or calls more expensive? What does it signal?
- Open interest by strike: where are the major positions?

### III. Event Trade Setups
- **Momentum play**: if revision momentum is strong + implied move is reasonable → directional bet
- **Straddle/strangle**: if implied move looks underpriced → buy vol pre-earnings
- **Iron condor/butterfly**: if implied move looks overpriced → sell vol
- **PEAD trade**: if surprise pattern suggests drift → enter post-earnings with options for leverage

### IV. Risk Parameters
- Maximum position size for earnings event trade
- Time decay risk: how much theta burn before the event?
- Gap risk: stock can gap beyond stop-loss → position sizing must account for this

Use load_skill for options analysis and event-driven strategy frameworks.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['options-advanced', 'options-strategy', 'event-driven', 'volatility'],
            "max_iterations": 50,
            "model_name": None,
        },
        "earnings_strategist": {
            "role": "Earnings Desk Strategist",
            "system_prompt": """You are the chief earnings strategist, responsible for synthesizing fundamental analysis, consensus dynamics, and options positioning into a final earnings trade recommendation with clear entry, exit, and risk parameters.

## Task
Deliver the final earnings trade recommendation for {target} based on all three research reports.

{upstream_context}

## Synthesis Requirements

### I. Signal Integration Table
| Dimension | Signal | Confidence | Source |
|-----------|--------|------------|--------|
| Fundamentals | bull/bear/neutral | H/M/L | Filing analysis |
| Revision momentum | up/down/flat | H/M/L | Consensus tracking |
| Options pricing | over/under/fair | H/M/L | Implied move analysis |

### II. Trade Recommendation
- **Pre-earnings trade**: [yes/no, direction, instrument, entry, stop, target]
- **Earnings event trade**: [straddle/directional/iron condor/skip]
- **Post-earnings PEAD trade**: [if surprise occurs, drift trade parameters]

### III. Position Sizing
- Pre-earnings position: max X% of portfolio (smaller due to event risk)
- Event trade: max X% of portfolio (defined risk via options)
- Post-earnings: max X% of portfolio (larger if conviction from surprise)

### IV. Decision Tree
```
If beat + raise guidance → [action]
If beat + maintain guidance → [action]
If miss + maintain guidance → [action]
If miss + lower guidance → [action]
```

### V. Key Dates
- Earnings date: [date]
- Options expiry around earnings: [date]
- Quiet period end / next guidance opportunity: [date]

Use load_skill for strategy generation and risk analysis.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest'],
            "skills": ['strategy-generate', 'risk-analysis', 'report-generate'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_fundamental", "type": "REASON", "agent": "fundamental_analyst"},
        {"name": "task_revision", "type": "REASON", "agent": "revision_tracker"},
        {"name": "task_options_event", "type": "REASON", "agent": "event_options_analyst"},
        {"name": "task_earnings_strategy", "type": "REASON", "agent": "earnings_strategist"},
    ],
    "variables": [{'name': 'target', 'description': 'Target stock (e.g., AAPL.US, NVDA.US, 700.HK, 600519.SH)', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_fundamental(state: State) -> dict:
    """REASON: Fundamental & Filing Analyst"""
    # Build context from state
    context = {
        "target": state.get("target", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("fundamental_analyst", context)
    log_event("task_fundamental", f"Completed: {len(result.summary)} chars")
    return {"task_fundamental_summary": result.summary}


async def task_revision(state: State) -> dict:
    """REASON: Earnings Revision & Consensus Tracker"""
    # Build context from state
    context = {
        "target": state.get("target", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("revision_tracker", context)
    log_event("task_revision", f"Completed: {len(result.summary)} chars")
    return {"task_revision_summary": result.summary}


async def task_options_event(state: State) -> dict:
    """REASON: Earnings Event & Options Analyst"""
    # Build context from state
    context = {
        "target": state.get("target", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("event_options_analyst", context)
    log_event("task_options_event", f"Completed: {len(result.summary)} chars")
    return {"task_options_event_summary": result.summary}


async def task_earnings_strategy(state: State) -> dict:
    """REASON: Earnings Desk Strategist"""
    # Build context from state
    context = {
        "target": state.get("target", ""),
        # Upstream summaries
        "fundamentals": state.get("task_fundamental_summary", ""),
        "revisions": state.get("task_revision_summary", ""),
        "options_event": state.get("task_options_event_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_fundamental_summary"):
        upstream_parts.append("## Fundamentals\n" + state["task_fundamental_summary"])
    if state.get("task_revision_summary"):
        upstream_parts.append("## Revisions\n" + state["task_revision_summary"])
    if state.get("task_options_event_summary"):
        upstream_parts.append("## Options Event\n" + state["task_options_event_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("earnings_strategist", context)
    log_event("task_earnings_strategy", f"Completed: {len(result.summary)} chars")
    return {"task_earnings_strategy_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_fundamental", task_fundamental)
    g.add_node("task_revision", task_revision)
    g.add_node("task_options_event", task_options_event)
    g.add_node("task_earnings_strategy", task_earnings_strategy)

    g.set_entry_point("task_fundamental")
    g.add_edge("task_fundamental", "task_earnings_strategy")
    g.add_edge("task_revision", "task_earnings_strategy")
    g.add_edge("task_options_event", "task_earnings_strategy")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_fundamental", "task_options_event")
    g.add_edge("task_fundamental", "task_revision")
    g.add_edge("task_earnings_strategy", END)

    return g.compile()
