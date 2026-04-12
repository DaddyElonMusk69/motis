---
name: operator-builder
description: Teach the Motis master agent how to decompose trading strategies into operators that conform to the operator contract and pass the Quality Gate.
category: builtin
---
# Operator Builder Skill

> **Purpose**: Teach the Motis master agent how to decompose trading strategies
> into operators that conform to the operator contract and pass the Quality Gate.
>
> **When to load**: Whenever the user asks to create, build, or modify a
> trading operator, strategy automation, or research pipeline.

## Operator Directory Convention

Each operator lives in its own folder under `operators/`:

```
operators/
├── examples/           # Reference implementations (for learning)
│   └── btc_smc_long/
│       ├── OPERATOR.md     # ← REQUIRED: discovery file
│       └── operator.py
├── builtin/            # Production-ready (ported from vibe trading swarms)
│   └── smc_swing/
│       ├── OPERATOR.md
│       ├── operator.py
│       └── prompts/    # Optional: hot-patchable prompt templates
└── user/               # Agent-generated operators (created via operator_create)
    └── my_strategy/
        ├── OPERATOR.md
        └── operator.py
```

**Rules:**
- Every operator folder MUST contain both `OPERATOR.md` and `operator.py`
- `OPERATOR.md` is the discovery file — the registry reads it to build the operator index
- `operator.py` is the executable contract (STATE, MANIFEST, build_graph)
- Agent-created operators always go to `operators/user/<name>/`
- Builtin operators are pre-built and version-controlled
- Each folder can also contain: `prompts/`, `config.yaml`, `tests/`
- Operator IDs follow the pattern: `<category>-<folder_name>` (e.g., `examples-btc_smc_long`)

---

## The Operator Contract

Every operator's `operator.py` exports exactly three things:

```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

# 1. STATE — TypedDict defining every field the graph reads or writes
class State(TypedDict):
    ohlcv: list[dict]
    signal: dict | None
    guard_approved: bool
    orders: list[dict]
    should_exit: bool
    run_log: list[dict]

STATE = State

# 2. MANIFEST — Metadata dict with name, type, risk config, trigger, nodes
MANIFEST = {
    "name": "My Strategy",
    "version": 1,
    "type": "paper_trade",           # paper_trade | live_trade | backtest | research
    "asset_class": "crypto_perp",
    "asset_universe": ["BTC/USDT:USDT"],
    "exchange": "hyperliquid",
    "trigger": {"type": "cron", "expression": "*/15 * * * *"},
    "risk": {
        "max_position_size_pct": 10.0,
        "max_daily_loss_pct": 5.0,
        "max_leverage": 3.0,
        "max_open_positions": 3,
        "risk_per_trade_pct": 2.0,
    },
    "reason_prompts": {
        "analyze_entry": "...",      # Hot-patchable via operator_update_prompt
    },
    "nodes": [
        {"name": "fetch_data",    "type": "DATA"},
        {"name": "analyze",       "type": "REASON"},
        {"name": "risk_guard",    "type": "GUARD"},
        {"name": "execute",       "type": "EXECUTE"},
    ],
}

# 3. build_graph() — Returns a compiled LangGraph StateGraph
def build_graph():
    g = StateGraph(State)
    # ... add nodes, edges, conditional edges ...
    return g.compile()
```

---

## The 5 Node Types

Classify **every step** in the strategy as one of these:

| Type | Nature | Rules |
|---|---|---|
| **DATA** | I/O | Fetches external data. MUST wrap in try/except. On failure → `should_exit = True`. |
| **COMPUTE** | Pure function | Deterministic math/logic. NO LLM calls. Reads state, returns computed values. |
| **REASON** | LLM call or agent loop | **Single-call**: `reason_call()` for quick decisions. **Agent-loop**: `run_agent()` for multi-step research. |
| **GUARD** | Deterministic | Checks risk limits from MANIFEST. Returns `guard_approved` bool. NEVER uses LLM. |
| **EXECUTE** | I/O | Calls `submit_order()`. MUST include `sl=` parameter. Only runs if guard approved. |

### Classification rules (use these exactly):
- "If it fetches external data → **DATA**"
- "If it's pure math/logic on state → **COMPUTE**"
- "If it needs a quick structured decision → **REASON** (single-call with `reason_call()`)"
- "If it needs multi-step research with tools → **REASON** (agent-loop with `run_agent()`)"
- "If it checks limits or thresholds → **GUARD**"
- "If it places or modifies orders → **EXECUTE**"

### CRITICAL: Deterministic vs. Subjective Judgment

Many trading decisions that **seem like judgment** are actually **deterministic logic**.

**Deterministic judgment (use COMPUTE, not REASON):**
- ✅ "Enter when fast MA crosses above slow MA" → if/else comparison
- ✅ "Exit when RSI > 70" → threshold check
- ✅ "Confirm BOS when price breaks structure high" → pattern matching logic
- ✅ "Size position based on ATR" → mathematical calculation
- ✅ "Detect candlestick patterns" → rule-based pattern recognition
- ✅ "Check if price is above/below a level" → comparison
- ✅ "Calculate signal strength from multiple indicators" → weighted formula

**Subjective judgment (use REASON):**
- ❌ "Is this a high-quality setup?" → needs context assessment
- ❌ "Does this fit the current macro environment?" → needs interpretation
- ❌ "Should I enter despite conflicting signals?" → needs weighing trade-offs
- ❌ "Is this pattern reliable in current market conditions?" → needs experience
- ❌ "Does the news sentiment support this trade?" → needs qualitative analysis
- ❌ "Should I override the signal based on intuition?" → discretionary override

**Rule of thumb:**
- **Can you write it as if/else/formula?** → COMPUTE
- **Do you need to "think about it" or consider context?** → REASON

**Examples:**

```python
# COMPUTE (deterministic) - MA crossover signal
def generate_signal(state):
    df = state["df"]
    current = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Pure logic - no LLM needed
    if prev["fast_ma"] <= prev["slow_ma"] and current["fast_ma"] > current["slow_ma"]:
        return {"signal": "long"}
    elif prev["fast_ma"] >= prev["slow_ma"] and current["fast_ma"] < current["slow_ma"]:
        return {"signal": "short"}
    else:
        return {"signal": None}

# REASON (subjective) - quality assessment
async def assess_setup(state):
    prompt = f"""
    The MA crossover signal is {state["signal"]}.
    Current market conditions: {state["market_context"]}
    Recent news: {state["news"]}
    
    Is this a high-quality setup worth taking?
    Consider: trend strength, volatility, news sentiment, confluence with other signals.
    """
    assessment = await reason_call(prompt=prompt)
    return {"approved": assessment["approved"]}
```

**When to skip REASON nodes entirely:**
- Strategy is fully rule-based (MA crossover, RSI, Bollinger, SMC structure)
- All decisions can be expressed as if/else/formulas
- Need exact reproducibility (backtesting must match live)
- Speed is critical (no LLM latency)
- Cost is a concern (no API costs per tick)

**Result:** Many operators will have ZERO REASON nodes - this is correct and preferred for production trading.

---

## The SDK Surface

Five functions available in every node:

```python
from agent.operator_sdk import call_skill, reason_call, run_agent, submit_order, log_event

# DATA/COMPUTE nodes: fetch data or run skills
ohlcv = await call_skill("data.ohlcv", {"symbol": "BTC/USDT:USDT", "interval": "4h", "limit": 300})

# REASON nodes (single-call): LLM call with structured output
signal = await reason_call(prompt="...", response_format={"type": "json_object"})

# REASON nodes (agent-loop): spawn scoped sub-agent for multi-step work
result = await run_agent("funding_analyst", {
    "target": state["target"],
    "timeframe": state["timeframe"],
})
# result.summary — the agent's output text
# result.artifacts — any files the agent produced

# EXECUTE nodes: place orders (MUST include sl=)
order = await submit_order(
    symbol="BTC/USDT:USDT",
    side="buy",
    size_pct=0.02,
    order_type="market",
    sl=98000.0,       # ← MANDATORY — hard stop-loss
    tp=105000.0,      # ← optional take-profit
)

# ALL nodes: structured logging for observability
log_event("node_name", "Human-readable message", data={"key": "value"})
```

### `run_agent()` — when to use it

- Use `reason_call()` when you need a **single structured decision** (e.g., "long or flat?")
- Use `run_agent()` when the node needs to **do real work** — fetch data, run tools, write reports

`run_agent(agent_id, context)` looks up `MANIFEST["agents"][agent_id]` and spawns
a new, lightweight agent instance with:
- Its own system prompt, tool whitelist, skill whitelist
- The user's model (or a per-agent model override)
- Its own iteration limit (not the master agent's loop)

The spawned agent does NOT inherit the master agent's memory or conversation.

### Platform Networking Boundary

When an operator runs on the Motis platform, spawned agents do **not** get to bypass
infrastructure boundaries.

- External web research and market data must go through Motis-owned MCP-backed tools
  such as `web_search`, `read_url`, and `call_skill("data.*")` / `call_skill("research.*")`
- Do **not** generate operator or sub-agent code that uses raw `httpx`, `requests`,
  `ccxt`, `yfinance`, or `bash` + `curl` for external networking in platform mode
- Do **not** place live orders from sub-agent reasoning code; execution stays in
  explicit EXECUTE nodes via `submit_order()`
- Standalone/dev mode may swap these backends to direct adapters later, but the
  operator contract should target the logical Motis interface first

### MANIFEST `agents` section

When using `run_agent()`, declare agents in the MANIFEST:

```python
MANIFEST = {
    ...
    "agents": {
        "funding_analyst": {
            "role": "Funding Rate & Basis Analyst",
            "system_prompt": "You are a senior derivatives analyst...",
            "tools": ["read_file", "load_skill", "web_search", "read_url"],
            "skills": ["perp-funding-basis", "okx-market"],
            "max_iterations": 50,
            "model_name": None,  # None = user's default model
        },
    },
    "nodes": [
        {"name": "funding_analysis", "type": "REASON", "agent": "funding_analyst"},
    ],
}
```

---

## The Quality Gate (10-Point Checklist)

Before an operator can graduate from `draft` → `paper`, these 5 MUST pass:

### Blocker Checks (all must pass for paper trading)

1. **hard_stop_loss** — Every `submit_order()` call includes `sl=` parameter
2. **position_sizing_cap** — Size calculation includes `min()` or cap logic
3. **daily_loss_killswitch** — A GUARD node reads daily_pnl and can halt the operator
4. **leverage_cap** — Leverage never exceeds `MANIFEST["risk"]["max_leverage"]`
5. **error_handling** — All `call_skill()` calls in DATA nodes wrapped in try/except

### Structural Checks (should pass — warnings only)

6. **state_completeness** — Every STATE field is written by at least one node
7. **guard_before_execute** — A GUARD node runs between REASON and EXECUTE
8. **logging** — Every node calls `log_event()` at least once

### Performance Checks (must pass for live trading)

9. **backtest_sharpe** — Backtest Sharpe ratio > 0.5
10. **backtest_max_drawdown** — Max drawdown < 2× daily loss threshold

---

## Decomposition Checklist

**Before generating code, you MUST list:**

```
1. Every step in the strategy
2. Each step's node type (DATA / COMPUTE / REASON / GUARD / EXECUTE)
3. For each step: explain WHY it's that node type
   - If COMPUTE: what formula/logic is used?
   - If REASON: what subjective judgment is needed?
4. For REASON nodes: single-call (reason_call) or agent-loop (run_agent)?
5. If agent-loop: what tools and skills does this agent need, and which external I/O paths must stay MCP-backed?
6. What state fields each step reads
7. What state fields each step writes
8. Where errors can occur and how they're handled
9. What the GUARD nodes check
```

**IMPORTANT:** Challenge yourself - can any REASON node be converted to COMPUTE?
- If the decision is rule-based, use COMPUTE
- Only use REASON for truly subjective judgment

Show this decomposition to the user and get approval before generating code.

---

## Canonical Graph Shapes

### 1. Pure Deterministic (NO REASON nodes)
```
DATA → COMPUTE → COMPUTE → GUARD → EXECUTE
       (signal)  (sizing)
```
**Use for:** MA crossover, RSI, Bollinger, SMC structure, mean reversion
**Characteristics:** Zero LLM calls, fully reproducible, fast, cheap

### 2. Linear Pipeline with LLM Filter (most common hybrid)
```
DATA → COMPUTE → REASON → COMPUTE(sizing) → GUARD → EXECUTE
       (signal)  (filter)
```
**Use for:** Rule-based signal + LLM confirms quality

### 3. Fan-Out / Fan-In (multi-asset)
```
     ┌─ DATA(BTC) → COMPUTE ─┐
DATA─┤                         ├─ REASON → GUARD → EXECUTE
     └─ DATA(ETH) → COMPUTE ─┘
```

### 4. Conditional Loop (event-driven)
```
DATA → COMPUTE → REASON ──[no signal]──→ END
                    │
               [signal]
                    ▼
            COMPUTE(size) → GUARD → EXECUTE
```

### 5. Research Pipeline (no execution)
```
DATA → COMPUTE → REASON → REPORT(save to memory)
```

### 6. Multi-Agent Research Team (from swarm presets)
```
                    ┌─ REASON(analyst₁) ─┐
DATA(fetch_meta) ──┼─ REASON(analyst₂) ─┼─ REASON(synthesizer) → END
                    └─ REASON(analyst₃) ─┘
```
Each REASON node uses `run_agent()` to spawn an independent agent loop.
The analysts run in parallel (LangGraph fan-out), the synthesizer waits
for all (fan-in) and produces the final report.

### 7. Multi-Agent Trading Desk (research + execution)
```
                    ┌─ REASON(analyst₁) ─┐
DATA(fetch_meta) ──┼─ REASON(analyst₂) ─┼─ REASON(synthesizer) → COMPUTE(sizing) → GUARD → EXECUTE
                    └─ REASON(analyst₃) ─┘
```
Extends shape 6 — the synthesizer's output feeds into position sizing,
risk gating, and order execution.

---

## Mandatory Anti-Patterns

**NEVER do these:**
- ❌ Skip stop-loss on any order
- ❌ Put risk-limit logic inside REASON nodes — REASON can be fooled, GUARD can't
- ❌ Hardcode API keys or exchange credentials
- ❌ Hardcode numbers in node functions — always read from MANIFEST["risk"]
- ❌ Let DATA node failures crash the operator — always try/except → should_exit
- ❌ Use raw `httpx` / `requests` / `ccxt` / `yfinance` or `bash` + `curl` for external networking in platform-mode operators or sub-agents
- ❌ Let sub-agents place live orders directly — keep execution in EXECUTE nodes via `submit_order()`

**ALWAYS do these:**
- ✅ Attach SL to every `submit_order()` call
- ✅ Handle DATA node failures with try/except → `{"should_exit": True}`
- ✅ Log in every node with `log_event()`
- ✅ Read risk limits from `MANIFEST["risk"]`, never hardcode
- ✅ Include conditional edges: if `should_exit` → END, if not `guard_approved` → END
- ✅ Put all risk logic in GUARD nodes (deterministic, not LLM-dependent)
- ✅ In platform mode, route sub-agent web/data access through MCP-backed logical tools (`web_search`, `read_url`, `call_skill("data.*")`, `call_skill("research.*")`)

---

## Complete Example: BTC SMC Long

```python
"""
BTC SMC Long — Buys BTC after a bullish BOS confirmed by
a liquidity sweep. 2% risk per trade. Hard SL below sweep low.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from agent.operator_sdk import call_skill, reason_call, submit_order, log_event


class State(TypedDict):
    ohlcv: list[dict]
    current_positions: list[dict]
    daily_pnl_usd: float
    smc_analysis: dict
    signal: Optional[dict]
    sized_signal: Optional[dict]
    guard_approved: bool
    guard_reason: str
    orders: list[dict]
    should_exit: bool
    run_log: list[dict]

STATE = State

MANIFEST = {
    "name": "BTC SMC Long",
    "version": 1,
    "type": "live_trade",
    "asset_class": "crypto_perp",
    "asset_universe": ["BTC/USDT:USDT"],
    "exchange": "hyperliquid",
    "trigger": {"type": "cron", "expression": "*/15 * * * *"},
    "risk": {
        "max_position_size_pct": 10.0,
        "max_daily_loss_pct": 5.0,
        "max_leverage": 3.0,
        "max_open_positions": 3,
        "risk_per_trade_pct": 2.0,
    },
    "reason_prompts": {
        "analyze_entry": (
            "You are a crypto trader specializing in SMC/ICT methodology.\n"
            "Analyze the following market structure for a valid LONG entry.\n\n"
            "Rules:\n"
            "- Only enter after a confirmed bullish BOS\n"
            "- A liquidity sweep must have occurred within the last 10 candles\n"
            "- Entry at or near a bullish order block\n"
            "- SL below the sweep low\n"
            "- TP at the next bearish OB or recent high\n\n"
            "Recent structure:\n{smc_summary}\n"
            "Current price: {current_price}\n\n"
            'Respond as JSON: {{"direction": "long"|"flat", "confidence": 0.0-1.0, '
            '"reasoning": "...", "entry": price, "sl": price, "tp": price}}'
        ),
    },
    "nodes": [
        {"name": "fetch_data",     "type": "DATA"},
        {"name": "calc_smc",       "type": "COMPUTE"},
        {"name": "analyze_entry",  "type": "REASON"},
        {"name": "size_position",  "type": "COMPUTE"},
        {"name": "risk_guard",     "type": "GUARD"},
        {"name": "execute_orders", "type": "EXECUTE"},
    ],
}


async def fetch_data(state: State) -> dict:
    """DATA: Fetch OHLCV + positions + daily P&L."""
    try:
        ohlcv = await call_skill("data.ohlcv", {
            "symbol": "BTC/USDT:USDT", "interval": "4h", "limit": 300,
        })
        positions = await call_skill("exchange.positions", {})
        daily_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
        log_event("fetch_data", f"Fetched {len(ohlcv)} candles, {len(positions)} positions")
        return {"ohlcv": ohlcv, "current_positions": positions, "daily_pnl_usd": daily_pnl}
    except Exception as e:
        log_event("fetch_data", f"Data fetch failed: {e}", data={"error": str(e)})
        return {"should_exit": True}


async def calc_smc(state: State) -> dict:
    """COMPUTE: Run SMC structure detection."""
    result = await call_skill("smc.structure", {"ohlcv": state["ohlcv"]})
    log_event("calc_smc", f"Found {len(result.get('bos_events', []))} BOS events")
    return {"smc_analysis": result}


async def analyze_entry(state: State) -> dict:
    """REASON: LLM decides whether to enter."""
    smc = state["smc_analysis"]
    prompt = MANIFEST["reason_prompts"]["analyze_entry"].format(
        smc_summary=str({
            "bos_events": smc.get("bos_events", [])[-5:],
            "liquidity_sweeps": smc.get("liquidity_sweeps", [])[-3:],
            "order_blocks": smc.get("order_blocks", [])[-3:],
        }),
        current_price=state["ohlcv"][-1]["close"],
    )
    signal = await reason_call(prompt=prompt, response_format={"type": "json_object"})
    if signal.get("direction") == "flat" or signal.get("confidence", 0) < 0.6:
        log_event("analyze_entry", "No valid entry", data=signal)
        return {"signal": None, "should_exit": True}
    log_event("analyze_entry", f"Signal: {signal['direction']} @ conf={signal['confidence']}")
    return {"signal": signal}


async def size_position(state: State) -> dict:
    """COMPUTE: Deterministic position sizing — 2% risk per trade."""
    signal = state.get("signal")
    if not signal:
        return {"should_exit": True}
    entry, sl = signal["entry"], signal["sl"]
    risk_distance_pct = abs(entry - sl) / entry
    risk_pct = MANIFEST["risk"]["risk_per_trade_pct"] / 100
    max_size_pct = MANIFEST["risk"]["max_position_size_pct"] / 100
    size_pct = min(risk_pct / risk_distance_pct, max_size_pct) if risk_distance_pct > 0 else 0
    size_pct = min(size_pct, MANIFEST["risk"]["max_leverage"] * risk_pct)
    log_event("size_position", f"Size: {size_pct:.2%} of capital")
    return {"sized_signal": {**signal, "size_pct": size_pct}}


async def risk_guard(state: State) -> dict:
    """GUARD: Baked-in risk checks — deterministic, no LLM."""
    risk = MANIFEST["risk"]
    reasons = []
    # 1. Max open positions
    open_count = len([p for p in state.get("current_positions", []) if p.get("size", 0) != 0])
    if open_count >= risk["max_open_positions"]:
        reasons.append(f"Max positions ({open_count}/{risk['max_open_positions']})")
    # 2. Signal must have SL
    sized = state.get("sized_signal")
    if sized and not sized.get("sl"):
        reasons.append("Missing stop-loss")
    # 3. SL distance sanity
    if sized and sized.get("sl") and sized.get("entry"):
        sl_dist = abs(sized["entry"] - sized["sl"]) / sized["entry"]
        if sl_dist < 0.001:
            reasons.append(f"SL too tight ({sl_dist:.4%})")
        if sl_dist > 0.10:
            reasons.append(f"SL too wide ({sl_dist:.4%})")
    approved = len(reasons) == 0
    log_event("risk_guard", f"{'APPROVED' if approved else 'REJECTED'}: {reasons or 'all clear'}")
    return {"guard_approved": approved, "guard_reason": "; ".join(reasons) or "approved"}


async def execute_orders(state: State) -> dict:
    """EXECUTE: Submit order with SL/TP attached."""
    if state.get("should_exit") or not state.get("guard_approved"):
        return {"orders": []}
    sized = state["sized_signal"]
    order = await submit_order(
        symbol="BTC/USDT:USDT", side="buy",
        size_pct=sized["size_pct"], order_type="market",
        sl=sized["sl"],           # ← MANDATORY
        tp=sized.get("tp"),
    )
    log_event("execute_orders", f"Order submitted: {order}")
    return {"orders": [order]}


def build_graph():
    g = StateGraph(State)
    g.add_node("fetch_data", fetch_data)
    g.add_node("calc_smc", calc_smc)
    g.add_node("analyze_entry", analyze_entry)
    g.add_node("size_position", size_position)
    g.add_node("risk_guard", risk_guard)
    g.add_node("execute_orders", execute_orders)
    g.set_entry_point("fetch_data")
    g.add_conditional_edges("fetch_data",
        lambda s: "exit" if s.get("should_exit") else "continue",
        {"exit": END, "continue": "calc_smc"})
    g.add_edge("calc_smc", "analyze_entry")
    g.add_conditional_edges("analyze_entry",
        lambda s: "exit" if s.get("should_exit") else "continue",
        {"exit": END, "continue": "size_position"})
    g.add_edge("size_position", "risk_guard")
    g.add_conditional_edges("risk_guard",
        lambda s: "execute" if s.get("guard_approved") else "exit",
        {"execute": "execute_orders", "exit": END})
    g.add_edge("execute_orders", END)
    return g.compile()
```

---

## OPERATOR.md — The Discovery File

Every operator you create MUST include an `OPERATOR.md` alongside `operator.py`.
This is a short, scannable summary that the registry reads for the system prompt.

**Required format:**

```markdown
# Operator Name

> One-line summary of what this operator does.

**Type:** paper_trade | live_trade | backtest | research
**Asset Class:** crypto_perp | us_equity | cn_a_share | multi_asset
**Exchange:** hyperliquid | binance | okx | (blank for research)
**Trigger:** cron `*/15 * * * *` | webhook | manual

## What It Does

2-4 sentences describing the strategy logic or research workflow.

## Agents (if multi-agent)

- **agent_name** — Role description (1 line)

## Graph Shape

```
DATA → COMPUTE → REASON → GUARD → EXECUTE
```

## When To Use

1-2 sentences: what kind of user request triggers this operator?
```

**Rules:**
- `# Operator Name` heading MUST match `MANIFEST["name"]`
- `> One-line summary` appears in the system prompt operator index
- Keep under 30 lines total
- Agents section only for multi-agent operators

---

## Workflow Summary

```
User intent (natural language)
        │
        ▼
1. Load this SKILL.md
        │
        ▼
2. Decompose strategy into steps
   Classify each as DATA / COMPUTE / REASON / GUARD / EXECUTE
   Show decomposition to user for approval
        │
        ▼
3. Generate TWO files:
   a. OPERATOR.md  (discovery — name, summary, graph shape, when to use)
   b. operator.py  (contract — STATE + MANIFEST + build_graph + node functions)
        │
        ▼
4. Run Quality Gate (10-point checklist)
   ├── Pass → operator_create() to store as DRAFT
   └── Fail → fix code, re-run gate
        │
        ▼
5. Recommend paper trading → operator_invoke()
        │
        ▼
6. User confirms → go LIVE
```
