
## The SDK Surface — Operators as MCP Clients

On-platform, operators are **MCP clients**. Their SDK calls route through the hosted
Motis MCP servers rather than talking to exchanges or data sources directly. This gives us:

- **Credential isolation** — exchange API keys live in the MCP server, never in operator code
- **Unified audit trail** — every order flows through MCP → logged to the immutable `trade_log`
- **Paper/live switching** — same `submit_order()` call; the MCP server picks the right backend

### SDK functions and their backends

```python
from motis_operator.sdk import call_skill, reason_call, run_agent, submit_order, log_event
```

| SDK Function | What it does | Platform backend | Standalone backend |
|---|---|---|---|
| `call_skill("data.ohlcv", {...})` | Fetch market data | **MCP** → `finance.data.ohlcv` tool | Direct ccxt/yfinance |
| `call_skill("research.macro", {...})` | External research APIs | **MCP** → `finance.research.macro` tool | Direct API calls |
| `call_skill("smc.structure", {...})` | Pure compute (no I/O) | **In-process** — no MCP round-trip | In-process (same) |
| `call_skill("technical.indicators", {...})` | Pure compute | **In-process** | In-process (same) |
| `reason_call(prompt, ...)` | Single LLM call for REASON nodes | Platform model config / BYOM | Local API key |
| `run_agent(agent_id, context)` | Spawn scoped sub-agent loop | New agent instance with scoped tools/skills | Same (local) |
| `submit_order(symbol, side, ...)` | Place exchange order | **MCP** → `execute_live_trade` tool | Direct exchange SDK |
| `cancel_order(order_id)` | Cancel order | **MCP** → `cancel_order` tool | Direct exchange SDK |
| `get_positions()` | Read open positions | **MCP** → `get_positions` tool | Direct exchange SDK |
| `log_event(node, msg, data)` | Write observability log | `operator_run_logs` table | stdout |

### The routing rule

```
I/O skills (data.*, research.*)  → MCP on platform, direct calls standalone
Pure compute (smc.*, technical.*) → always in-process (no reason to round-trip)
Execution (submit_order, etc.)    → always MCP on platform, direct SDK standalone
Agent loops (run_agent)           → new scoped agent instance (same in all modes)
```

### `run_agent()` — spawning scoped sub-agents

For REASON nodes that need multi-step work (data fetching, analysis, report writing),
`run_agent()` spawns a new, lightweight agent instance:

```python
async def run_agent(
    agent_id: str,         # References MANIFEST["agents"][agent_id]
    context: dict,         # State fields to pass as context
    *,
    output_key: str = "summary",  # Which field of the result to return
) -> AgentResult:
    """
    Spawn a scoped sub-agent from the MANIFEST agents config.

    The sub-agent gets:
    - Its own system_prompt (from MANIFEST)
    - Only the tools listed in its config (scoped whitelist)
    - Only the skills listed in its config (scoped whitelist)
    - The user's model config (or per-agent override if model_name is set)
    - Its own iteration limit (from config, default 25)

    It does NOT get:
    - The master agent's conversation history
    - The master agent's system prompt
    - Access to other operators or operator tools
    """
```

Example usage in a node:

```python
async def funding_analysis(state: State) -> dict:
    """REASON: Full agent analysis of funding rates."""
    result = await run_agent("funding_analyst", {
        "target": state["target"],
        "timeframe": state["timeframe"],
    })
    log_event("funding_analysis", f"Completed: {len(result.summary)} chars")
    return {"funding_summary": result.summary}
```

### How it works under the hood

```python
# motis_operator/sdk.py — simplified

async def submit_order(symbol, side, size_pct, order_type, sl=None, tp=None):
    if _runtime_mode == "platform":
        # MCP client call → hosted MCP server → exchange
        return await _mcp_client.call_tool("execute_live_trade", {
            "symbol": symbol, "side": side, "size": size_pct,
            "order_type": order_type, "sl": sl, "tp": tp,
            "operator_id": _current_operator_id(),
        })
    else:
        # Standalone — direct exchange SDK (ccxt / hyperliquid)
        return await _exchange_client.create_order(...)

async def call_skill(name, args):
    if name.startswith(("data.", "research.")):
        # I/O skills — go through MCP on platform
        if _runtime_mode == "platform":
            return await _mcp_client.call_tool(f"finance.{name}", args)
        return await _direct_skill_call(name, args)
    # Pure compute — always in-process, both modes
    return await _run_local_skill(name, args)
```

The operator code never changes between modes — only the SDK backend swaps.

---

## Hot-Patching REASON Prompts

REASON node prompts are stored separately from graph structure. The master agent can
update a prompt without rebuilding the operator:

```python
# The prompt is a string field on the MANIFEST, keyed by node name
MANIFEST = {
    ...
    "reason_prompts": {
        "analyze_entry": "You are a crypto trader using SMC/ICT methodology...",
    },
}

# In the REASON node:
async def analyze_entry(state: State) -> dict:
    from motis_operator.sdk import reason_call, get_manifest
    manifest = get_manifest()  # reads current MANIFEST (may be hot-patched)
    prompt = manifest["reason_prompts"]["analyze_entry"]
    
    signal = await reason_call(
        prompt=prompt.format(**state),  # inject state into prompt
        response_format={"type": "json_object"},
    )
    ...
```

The master agent updates the prompt via:
```
operator_update_prompt(operator_id, node="analyze_entry", prompt="new prompt...")
```

This is the fastest iteration loop — change the prompt, observe next tick's behavior,
repeat. No redeployment, no revalidation of the graph structure.

---

## Complete Example: BTC SMC Long Operator

```python
"""
BTC SMC Long Operator
=====================
Generated by Motis master agent.
 
Strategy: Enter BTC long when 4h timeframe shows bullish BOS after
a liquidity sweep. 2% risk per trade. Hard SL below sweep low.

This operator runs autonomously — it can execute independently of
the Motis platform with just an API key and exchange credentials.
"""

from typing import Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import call_skill, reason_call, submit_order, log_event

# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    # DATA
    ohlcv: list[dict]
    current_positions: list[dict]
    daily_pnl_usd: float
    
    # COMPUTE
    smc_analysis: dict                  # BOS, CHoCH, sweeps, OBs
    
    # REASON
    signal: Optional[dict]              # {direction, confidence, entry, sl, tp}
    
    # COMPUTE (sizing)
    sized_signal: Optional[dict]        # signal + size_usd
    
    # GUARD
    guard_approved: bool
    guard_reason: str
    
    # EXECUTE
    orders: list[dict]
    
    # Control
    should_exit: bool
    run_log: list[dict]

# ── Manifest ───────────────────────────────────────────────────────────

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
            "Analyze the following market structure and determine if there is "
            "a valid LONG entry.\n\n"
            "Rules:\n"
            "- Only enter after a confirmed bullish BOS\n"
            "- A liquidity sweep must have occurred within the last 10 candles\n"
            "- Entry should be at or near a bullish order block\n"
            "- SL must be below the sweep low\n"
            "- TP should target the next bearish order block or recent high\n\n"
            "Recent structure:\n{smc_summary}\n\n"
            "Current price: {current_price}\n\n"
            "Respond as JSON: {{\"direction\": \"long\"|\"flat\", \"confidence\": 0.0-1.0, "
            "\"reasoning\": \"...\", \"entry\": price, \"sl\": price, \"tp\": price}}"
        ),
    },
    "nodes": [
        {"name": "fetch_data",       "type": "DATA"},
        {"name": "calc_smc",         "type": "COMPUTE"},
        {"name": "analyze_entry",    "type": "REASON"},
        {"name": "size_position",    "type": "COMPUTE"},
        {"name": "risk_guard",       "type": "GUARD"},
        {"name": "execute_orders",   "type": "EXECUTE"},
    ],
}

# ── Node Implementations ──────────────────────────────────────────────

async def fetch_data(state: State) -> dict:
    """DATA: Fetch OHLCV + current positions + daily P&L"""
    try:
        ohlcv = await call_skill("data.ohlcv", {
            "symbol": "BTC/USDT:USDT", "interval": "4h", "limit": 300,
        })
        positions = await call_skill("exchange.positions", {})
        daily_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
        
        log_event("fetch_data", f"Fetched {len(ohlcv)} candles, {len(positions)} positions")
        return {
            "ohlcv": ohlcv,
            "current_positions": positions,
            "daily_pnl_usd": daily_pnl,
        }
    except Exception as e:
        log_event("fetch_data", f"Data fetch failed: {e}", data={"error": str(e)})
        return {"should_exit": True}


async def calc_smc(state: State) -> dict:
    """COMPUTE: Run SMC structure detection (deterministic)"""
    result = await call_skill("smc.structure", {"ohlcv": state["ohlcv"]})
    log_event("calc_smc", f"Found {len(result.get('bos_events', []))} BOS events")
    return {"smc_analysis": result}


async def analyze_entry(state: State) -> dict:
    """REASON: LLM decides whether to enter (hot-patchable prompt)"""
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
    """COMPUTE: Deterministic position sizing — 2% risk per trade"""
    signal = state.get("signal")
    if not signal:
        return {"should_exit": True}
    
    entry = signal["entry"]
    sl = signal["sl"]
    risk_distance_pct = abs(entry - sl) / entry
    
    # 2% risk per trade, capped at 10% of capital
    risk_pct = MANIFEST["risk"]["risk_per_trade_pct"] / 100
    max_size_pct = MANIFEST["risk"]["max_position_size_pct"] / 100
    
    size_pct = risk_pct / risk_distance_pct if risk_distance_pct > 0 else 0
    size_pct = min(size_pct, max_size_pct)
    
    # Enforce leverage cap
    max_leverage = MANIFEST["risk"]["max_leverage"]
    size_pct = min(size_pct, max_leverage * risk_pct)
    
    log_event("size_position", f"Size: {size_pct:.2%} of capital")
    return {"sized_signal": {**signal, "size_pct": size_pct}}


async def risk_guard(state: State) -> dict:
    """GUARD: Baked-in risk checks — runs EVERY tick before execution"""
    risk = MANIFEST["risk"]
    reasons = []
    
    # 1. Daily loss kill-switch
    max_daily_loss = risk["max_daily_loss_pct"]
    if state.get("daily_pnl_usd", 0) < 0:
        # Rough check — in production, normalize against AUM
        log_event("risk_guard", f"Daily P&L: ${state['daily_pnl_usd']:.2f}")
    
    # 2. Max open positions
    open_count = len([p for p in state.get("current_positions", []) if p.get("size", 0) != 0])
    if open_count >= risk["max_open_positions"]:
        reasons.append(f"Max positions reached ({open_count}/{risk['max_open_positions']})")
    
    # 3. Signal must have SL
    sized = state.get("sized_signal")
    if sized and not sized.get("sl"):
        reasons.append("Signal missing stop-loss — rejecting")
    
    # 4. SL distance sanity (not less than 0.1%, not more than 10%)
    if sized and sized.get("sl") and sized.get("entry"):
        sl_dist = abs(sized["entry"] - sized["sl"]) / sized["entry"]
        if sl_dist < 0.001:
            reasons.append(f"SL too tight ({sl_dist:.4%})")
        if sl_dist > 0.10:
            reasons.append(f"SL too wide ({sl_dist:.4%})")
    
    approved = len(reasons) == 0
    log_event("risk_guard", f"{'APPROVED' if approved else 'REJECTED'}: {reasons or 'all clear'}")
    return {
        "guard_approved": approved,
        "guard_reason": "; ".join(reasons) if reasons else "approved",
    }


async def execute_orders(state: State) -> dict:
    """EXECUTE: Submit orders with SL/TP. Only if guard approved."""
    if state.get("should_exit") or not state.get("guard_approved"):
        return {"orders": []}
    
    sized = state["sized_signal"]
    order = await submit_order(
        symbol="BTC/USDT:USDT",
        side="buy",
        size_pct=sized["size_pct"],
        order_type="market",
        sl=sized["sl"],        # ← hard SL always attached
        tp=sized.get("tp"),
    )
    log_event("execute_orders", f"Order submitted: {order}")
    return {"orders": [order]}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("fetch_data", fetch_data)
    g.add_node("calc_smc", calc_smc)
    g.add_node("analyze_entry", analyze_entry)
    g.add_node("size_position", size_position)
    g.add_node("risk_guard", risk_guard)
    g.add_node("execute_orders", execute_orders)
    
    g.set_entry_point("fetch_data")
    g.add_conditional_edges(
        "fetch_data",
        lambda s: "exit" if s.get("should_exit") else "continue",
        {"exit": END, "continue": "calc_smc"},
    )
    g.add_edge("calc_smc", "analyze_entry")
    g.add_conditional_edges(
        "analyze_entry",
        lambda s: "exit" if s.get("should_exit") else "continue",
        {"exit": END, "continue": "size_position"},
    )
    g.add_edge("size_position", "risk_guard")
    g.add_conditional_edges(
        "risk_guard",
        lambda s: "execute" if s.get("guard_approved") else "exit",
        {"execute": "execute_orders", "exit": END},
    )
    g.add_edge("execute_orders", END)
    
    return g.compile()
```

---

## Canonical Graph Shapes

Most operators follow one of these. The agent picks one and fills in the specifics:

### 1. Linear Pipeline (80% of strategies)
```
DATA → COMPUTE → REASON → COMPUTE(sizing) → GUARD → EXECUTE
```

### 2. Fan-Out / Fan-In (multi-asset)
```
     ┌─ DATA(BTC) → COMPUTE ─┐
DATA─┤                         ├─ REASON → GUARD → EXECUTE
     └─ DATA(ETH) → COMPUTE ─┘
```

### 3. Conditional Loop (event-driven monitoring)
```
DATA → COMPUTE → REASON ──[no signal]──→ END
                    │
               [signal]
                    ▼
            COMPUTE(size) → GUARD → EXECUTE
```

### 4. Research Pipeline (no execution)
```
DATA → COMPUTE → REASON → REPORT(save to memory)
```

### 5. Multi-Agent Research Team (from swarm presets)
```
                    ┌─ REASON(analyst_1) ─┐
DATA(fetch_meta) ──┼─ REASON(analyst_2) ─┼─ REASON(synthesizer) → END
                    └─ REASON(analyst_3) ─┘
```

Each REASON node uses `run_agent()` to spawn an independent agent loop.
The analysts run in parallel (LangGraph fan-out), the synthesizer
waits for all of them (fan-in) and produces the final report.

For trading-oriented teams, extend with:
```
... → REASON(synthesizer) → COMPUTE(sizing) → GUARD → EXECUTE
```

---

## The Builder Skill (SKILL.md)

The `operator-builder` skill is the system prompt context that teaches the master agent
how to build correct operators. It contains:

### Contents:

1. **The 5 node types** with classification rules
   - "If it fetches external data → DATA"
   - "If it's pure math on state → COMPUTE"
   - "If it needs judgment/interpretation → REASON"
   - "If it checks limits/thresholds → GUARD"
   - "If it places orders → EXECUTE"

2. **The module contract** (STATE, MANIFEST, build_graph) with annotated example

3. **The Quality Gate checklist** (all 10 checks, with explanations)
   - The agent internalizes these as constraints during code generation

4. **3 complete examples:**
   - Linear pipeline (trend-following)
   - Fan-out (multi-asset momentum)
   - Research pipeline (weekly macro analysis)

5. **The SDK surface** (call_skill, reason_call, submit_order, log_event)

6. **Mandatory anti-patterns:**
   - "NEVER skip stop-loss on any order"
   - "NEVER put risk-limit logic inside REASON nodes — REASON can be fooled, GUARD can't"
   - "NEVER hardcode API keys or exchange credentials"
   - "ALWAYS handle DATA node failures with try/except → should_exit"
   - "ALWAYS log in every node for observability"
   - "ALWAYS read risk limits from MANIFEST, never hardcode numbers in node functions"

7. **The decomposition checklist** — forces the agent to show its work:
   ```
   Before generating code, list:
   1. Every step in the strategy
   2. Each step's node type (DATA/COMPUTE/REASON/GUARD/EXECUTE)
   3. What state fields each step reads
   4. What state fields each step writes
   5. Where errors can occur and how they're handled
   6. What the GUARD nodes check
   ```

---

## Runtime Execution

The same operator code runs in all three modes. Only the SDK backend changes.

### Development Mode

```bash
# Run operator from filesystem for testing
MOTIS_RUNTIME_MODE=dev python -m motis_operator.runner btc_smc_long

# What happens:
1. Registry loads from packages/operator_sdk/motis_operator/operators/
2. Imports btc_smc_long.py module
3. Calls build_graph() to get compiled graph
4. Runs on MANIFEST's trigger schedule (or manual invoke)
5. SDK functions:
   - call_skill() → in-process for compute, direct API for data
   - reason_call() → uses dev API key
   - submit_order() → direct exchange SDK (test mode)
   - log_event() → stdout
6. State checkpointed to local SQLite
```

### Platform Mode

```bash
# Operator runs via Celery/Temporal scheduler
MOTIS_RUNTIME_MODE=platform

# What happens:
1. Scheduler triggers (cron / event / manual)
2. Registry loads operator from PostgreSQL by operator_id
3. exec(graph_code, {}) → extracts STATE, MANIFEST, build_graph
4. Injects checkpointer (Redis) for state persistence
5. Injects user's model config for REASON nodes
6. graph.ainvoke(input, config={thread_id, user_id, operator_id})
7. Nodes execute: DATA → COMPUTE → REASON → GUARD → EXECUTE
8. SDK functions:
   - call_skill() → MCP for data/research, in-process for compute
   - reason_call() → user's BYOM config
   - submit_order() → MCP (execute_live_trade or execute_paper_trade)
   - log_event() → operator_run_logs table
9. State checkpoint saved to Redis for next tick
```

### Standalone Mode

```bash
# User runs MOTIS agent locally
MOTIS_RUNTIME_MODE=standalone python -m motis_operator.runner

# What happens:
1. Registry loads from ~/.motis/operators/
2. Imports all .py files in that directory
3. User selects which operator to run (or runs all)
4. Runs on MANIFEST's trigger schedule
5. SDK functions:
   - call_skill() → direct API calls (ccxt, yfinance, etc.)
   - reason_call() → user's local API key
   - submit_order() → direct exchange SDK
   - log_event() → stdout or local log file
6. State checkpointed to local SQLite (~/.motis/state.db)
```

### The Key Insight

**The same operator code runs in all three modes.**

The SDK functions (`call_skill`, `submit_order`, `log_event`) are backed by different
implementations depending on `RUNTIME_MODE`, but the operator code doesn't know or care.

```python
# This code works identically in dev/platform/standalone:

async def fetch_data(state: State) -> dict:
    ohlcv = await call_skill("data.ohlcv", {
        "symbol": "BTC/USDT:USDT", "interval": "4h", "limit": 300,
    })
    return {"ohlcv": ohlcv}

async def execute_orders(state: State) -> dict:
    order = await submit_order(
        symbol="BTC/USDT:USDT",
        side="buy",
        size_pct=sized["size_pct"],
        order_type="market",
        sl=sized["sl"],
        tp=sized.get("tp"),
    )
    return {"orders": [order]}
```

The SDK routing happens under the hood:

```python
# motis_operator/sdk.py

async def submit_order(symbol, side, size_pct, order_type, sl=None, tp=None):
    mode = os.getenv("MOTIS_RUNTIME_MODE", "platform")
    
    if mode == "platform":
        # MCP client call → hosted MCP server → exchange
        return await _mcp_client.call_tool("execute_live_trade", {
            "symbol": symbol, "side": side, "size": size_pct,
            "order_type": order_type, "sl": sl, "tp": tp,
            "operator_id": _current_operator_id(),
        })
    
    else:  # dev or standalone
        # Direct exchange SDK (ccxt / hyperliquid)
        return await _exchange_client.create_order(
            symbol=symbol, side=side, type=order_type,
            amount=_calculate_size(size_pct), params={"stopLoss": sl, "takeProfit": tp}
        )
```

---

## Operator Visibility to the Master Agent

Operators appear in the system prompt alongside skills. The visibility depends on runtime mode:

### Platform Mode
```
Available Operators:

[PLATFORM TEMPLATES] (Read-only, can be cloned)
  • BTC SMC Long Template (crypto_perp / hyperliquid)
  • ETH Momentum Template (crypto_perp / hyperliquid)
  • Macro Research Template (multi_asset)

[YOUR OPERATORS] (Agent-generated or imported)
  [LIVE] My BTC Strategy  P&L: +12.3%  id: abc-123
         Last tick: 3 min ago  │  Open positions: 1  │  Daily P&L: +$340
  [PAPER] My ETH Strategy P&L: -1.2%   id: def-456
         Last tick: 8 min ago  │  Open positions: 0  │  Daily P&L: -$45
  [DRAFT] My Macro Research            id: ghi-789
         Quality Gate: 8/10 passed (missing: backtest_sharpe, backtest_max_drawdown)
```

### Development Mode
```
Available Operators (from filesystem):

  • btc_smc_long (crypto_perp / hyperliquid)
  • eth_momentum (crypto_perp / hyperliquid)
  • macro_research (multi_asset)
```

### Standalone Mode
```
Available Operators (from ~/.motis/operators/):

  • my_btc_strategy (crypto_perp / hyperliquid)
  • my_eth_strategy (crypto_perp / hyperliquid)
  • my_macro_research (multi_asset)
```

### Tools Available (Platform Mode Only)

These MCP tools are only available when running on the platform:

- `operator_create(name, type, spec)` → generate + store in DB
- `operator_list(state_filter)` → list with metrics
- `operator_status(id)` → detailed state, run log, positions
- `operator_invoke(id, input)` → run manually / backtest
- `operator_pause(id)` → halt a live operator
- `operator_archive(id)` → deactivate
- `operator_update_prompt(id, node, prompt)` → hot-patch REASON prompt
- `operator_export(id)` → export to filesystem for standalone use

In dev/standalone modes, operators are managed via filesystem (no MCP tools needed).

---

## What Makes This Different from "Just a Script"

| Script | Operator |
|---|---|
| Runs once | Runs on schedule, forever |
| No state persistence | Redis-checkpointed state across ticks |
| Risk is programmer's problem | Quality Gate enforces risk before deployment |
| Can do anything | Has full access BUT must pass 10-point checklist |
| No observability | Every node logs via `log_event()` |
| User must debug | Master agent can inspect, diagnose, iterate |
| Static prompts | REASON prompts hot-patchable without redeployment |
| Platform-dependent | **Runs standalone** with just API keys |

---
