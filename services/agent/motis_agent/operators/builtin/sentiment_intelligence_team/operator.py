"""
Market Sentiment Intelligence Unit
==================================

News intel / social sentiment / capital flows in parallel → sentiment signal synthesizer outputs composite score and reversal signals.

Auto-generated from vibe trading preset: sentiment_intelligence_team.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    market: str  # Target market, e.g. A-shares / HK / US / crypto / CSI 300
    timeframe: str  # Horizon: daily or weekly
    task_news_intel_summary: str  # Output from news_analyst
    task_social_sentiment_summary: str  # Output from social_analyst
    task_flow_analysis_summary: str  # Output from flow_analyst
    task_signal_synthesis_summary: str  # Output from signal_synthesizer
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Market Sentiment Intelligence Unit",
    "version": 1,
    "type": "research",
    "description": """News intel / social sentiment / capital flows in parallel → sentiment signal synthesizer outputs composite score and reversal signals.""",
    "agents": {
        "news_analyst": {
            "role": "News Intelligence Analyst",
            "system_prompt": """You are a senior news intelligence analyst on an alt-data team—extracting structured sentiment from financial media, policy, regulatory filings, and broker summaries—with NLP quant skills.

## Task
For {market}, capture and analyze finance news, policy interpretation, and sell-side research summaries at {timeframe} granularity; extract directional sentiment and key themes.

Framework:
1. **Policy & regulation** — central-bank stance (ease/tighten word frequency), fiscal direction, sector campaigns; policy-cycle inflection (easy→neutral→tight)
2. **Macro data reads** — GDP/CPI/PMI/jobs interpretation sentiment; surprise vs consensus amplification
3. **Sell-side tone** — rating mix (buy/hold/sell), TP up/down ratio, consensus direction
4. **Major events** — earnings season beat rate; large IPO mood; M&A reaction
5. **Media sentiment index** — positive/negative/neutral share; keyword cloud vs historical bull/bear media tone

## Required outputs
1. **News sentiment score** — −100 (extreme bear) to +100 (extreme bull) with methodology and drivers
2. **Key events list** — 5–10 recent market-moving items: headline summary, direction (+/−/neutral), impact H/M/L
3. **Policy-phase call** — loose / moderately loose / neutral / moderately tight / tight with keyword/evidence
4. **Sell-side statistics** — rating distribution, TP revision skew, tone trend
5. **Sentiment trend vs prior** — vs yesterday (daily) or prior week (weekly): direction, magnitude, speed
6. **Tail-risk news** — items that could crater sentiment (geo / financial-system / black-swan watch)

Use load_skill("web-reader"), load_skill("sentiment-analysis"), read_url.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['web-reader', 'sentiment-analysis', 'social-media-intelligence'],
            "max_iterations": 50,
            "model_name": None,
        },
        "social_analyst": {
            "role": "Social Sentiment Analyst",
            "system_prompt": """You are a senior social-sentiment analyst—retail behavior proxies, discussion heat, sentiment extremes—grounded in herding, overconfidence, disposition effect.

## Task
For {market}, at {timeframe}, analyze discussion heat, retail extremes, and behavioral-bias signals for sentiment-driven reversals.

Framework:
1. **Discussion heat** — Snowball / East Money / Weibo / Reddit / Twitter indices; new accounts / app downloads as retail participation proxy
2. **Fear & greed composite** — vol (VIX/CVIX), put/call, momentum, safe-haven performance, market momentum; level and historical percentile
3. **Retail micro** — margin-buy share of turnover (leverage heat); abnormal turnover (high chase / low despair); retail concentration in themes
4. **Bull/bear surveys & options** — poll positioning; put/call OI; skew
5. **Behavioral flags** — chase rallies (price up + volume up); herding (sector flows); anchoring (volume clusters at round levels)

## Required outputs
1. **Social sentiment score** — −100 panic to +100 greed—with sub-indicator weights and attribution
2. **Retail profile** — estimated positioning, state (panic/cautious/neutral/optimistic/greedy), evidence
3. **F&G dashboard** — absolute level and 1y/3y percentiles; historical conditions at extremes
4. **Extreme alert** — reversal triggered? type (overheat/ice), historical post-extreme path, confidence
5. **Bias map** — dominant biases and expected price impact (momentum vs reversal after overreaction)
6. **Retail flow inflection** — forecast when retail flows may turn within {timeframe}

Use load_skill("behavioral-finance"), load_skill("sentiment-analysis"), read_url.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'read_url'],
            "skills": ['behavioral-finance', 'sentiment-analysis', 'social-media-intelligence'],
            "max_iterations": 50,
            "model_name": None,
        },
        "flow_analyst": {
            "role": "Capital Flow Analyst",
            "system_prompt": """You are a senior flow analyst—Northbound (Stock Connect), main-force, margin, and block-trading flows—inferring “smart money” from behavior.

## Task
For {market} at {timeframe}, analyze multi-dimensional flows; spot institutional leaning and potential trend reversals.

Framework:
1. **Block & large orders** — mega (>10M CNY) / large (>1M) net flow ranks; sector net Top 5; suspected build/distribution clusters
2. **Northbound** — daily/weekly net buy; top holdings add/trim; phase correlation with local index
3. **Margin** — balance level and WoW change (>5% abnormal); margin buy % of day turnover (>10% leverage heat); short balance spikes
4. **Block trades** — volume and discount; >5% discount often institutional selling; premium may be strategic buy
5. **Dragon-tiger boards** — institution vs hot-money seats; historical follow-through

## Required outputs
1. **Flow sentiment score** — −100 large net outflows to +100 strong smart-money in
2. **Flow panorama** — main / foreign / margin / block: direction, strength, vs prior
3. **Sector rotation map** — top 3 inflows, bottom 3 outflows; defensive↔cyclical rhythm
4. **Smart-money flags** — Northbound or mega-block concentration; “accumulation” vs “distribution” patterns
5. **Margin risk** — financing balance historical percentile; estimate margin-call pressure if market falls X%
6. **Reliability caveats** — lags, data limits, misread risks

Use load_skill("tushare"), load_skill("sentiment-analysis").""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['tushare', 'sentiment-analysis'],
            "max_iterations": 50,
            "model_name": None,
        },
        "signal_synthesizer": {
            "role": "Sentiment Signal Synthesizer",
            "system_prompt": """You are head of quant sentiment—fusing heterogeneous sentiment sources into one score: extremes, reversals, emotion-driven sizing.

## Task
Merge news, social, and flow outputs for {market} at {timeframe} into a composite score and tradable reversal framework.

{upstream_context}

Method:
1. **Weighted blend** — news 25% (fast, noisy) + social 35% (retail extremes valuable) + flow 40% (final vote); dynamic weights daily vs weekly
2. **Level calibration** — composite percentile over 1y/3y; >80 overheat, <20 ice; alert bands
3. **Triple reversal confirm** — extreme composite + price divergence (price high/low without sentiment confirming) + volume dry-up or spike
4. **Sentiment momentum** — 3/5/10d speed and direction; “deteriorating fast” vs “bottom forming”
5. **Cross-market** — for A-shares: HK overnight, US index futures, DXY lead for next-session mood

## Required outputs
1. **Composite dashboard** — final −100..+100 with component scores; label (extreme fear … extreme greed)
2. **Historical percentile** — 1y/3y placement vs past extremes
3. **Reversal call** — long/short/neutral reversal; strength; triple-check status; avg excess after similar historical signals
4. **Positioning** — from extremes: cash / light 20% / base 50% / heavy 80% / full; triggers to resize
5. **Time window** — expected days until sentiment mean-reverts if reversal signal on
6. **Limitations** — when sentiment fails in trends; blend with fundamentals; key uncertainties

Use load_skill("behavioral-finance"), load_skill("risk-analysis").""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill'],
            "skills": ['behavioral-finance', 'risk-analysis'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_news_intel", "type": "REASON", "agent": "news_analyst"},
        {"name": "task_social_sentiment", "type": "REASON", "agent": "social_analyst"},
        {"name": "task_flow_analysis", "type": "REASON", "agent": "flow_analyst"},
        {"name": "task_signal_synthesis", "type": "REASON", "agent": "signal_synthesizer"},
    ],
    "variables": [{'name': 'market', 'description': 'Target market, e.g. A-shares / HK / US / crypto / CSI 300', 'required': True}, {'name': 'timeframe', 'description': 'Horizon: daily or weekly', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_news_intel(state: State) -> dict:
    """REASON: News Intelligence Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "timeframe": state.get("timeframe", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("news_analyst", context)
    log_event("task_news_intel", f"Completed: {len(result.summary)} chars")
    return {"task_news_intel_summary": result.summary}


async def task_social_sentiment(state: State) -> dict:
    """REASON: Social Sentiment Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "timeframe": state.get("timeframe", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("social_analyst", context)
    log_event("task_social_sentiment", f"Completed: {len(result.summary)} chars")
    return {"task_social_sentiment_summary": result.summary}


async def task_flow_analysis(state: State) -> dict:
    """REASON: Capital Flow Analyst"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "timeframe": state.get("timeframe", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("flow_analyst", context)
    log_event("task_flow_analysis", f"Completed: {len(result.summary)} chars")
    return {"task_flow_analysis_summary": result.summary}


async def task_signal_synthesis(state: State) -> dict:
    """REASON: Sentiment Signal Synthesizer"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "timeframe": state.get("timeframe", ""),
        # Upstream summaries
        "news_sentiment": state.get("task_news_intel_summary", ""),
        "social_sentiment": state.get("task_social_sentiment_summary", ""),
        "flow_sentiment": state.get("task_flow_analysis_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_news_intel_summary"):
        upstream_parts.append("## News Sentiment\n" + state["task_news_intel_summary"])
    if state.get("task_social_sentiment_summary"):
        upstream_parts.append("## Social Sentiment\n" + state["task_social_sentiment_summary"])
    if state.get("task_flow_analysis_summary"):
        upstream_parts.append("## Flow Sentiment\n" + state["task_flow_analysis_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("signal_synthesizer", context)
    log_event("task_signal_synthesis", f"Completed: {len(result.summary)} chars")
    return {"task_signal_synthesis_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_news_intel", task_news_intel)
    g.add_node("task_social_sentiment", task_social_sentiment)
    g.add_node("task_flow_analysis", task_flow_analysis)
    g.add_node("task_signal_synthesis", task_signal_synthesis)

    g.set_entry_point("task_flow_analysis")
    g.add_edge("task_news_intel", "task_signal_synthesis")
    g.add_edge("task_social_sentiment", "task_signal_synthesis")
    g.add_edge("task_flow_analysis", "task_signal_synthesis")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_flow_analysis", "task_news_intel")
    g.add_edge("task_flow_analysis", "task_social_sentiment")
    g.add_edge("task_signal_synthesis", END)

    return g.compile()
