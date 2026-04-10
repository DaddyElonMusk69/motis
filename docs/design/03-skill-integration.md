# 03 — Skill Integration (Vibe Trading → Motis)

> **Status:** Final
> **Created:** 2026-04-10
> **Last updated:** 2026-04-10

---

## The Core Question

Vibe Trading is a **7-category callable skill library** for market intelligence. Motis has
a **master agent** that calls tools. The integration question is: _how do those two connect?_

The answer: Vibe Trading skills become OpenAI function-calling tools routed through the
`MotisToolRouter`. The agent never knows about "Vibe Trading" — it just has tools.

---

## What Vibe Trading Provides

| Category | Examples | Nature |
|---|---|---|
| `data` | OHLCV (ccxt, yfinance, akshare, tushare, okx), orderbook | Pure computation — no state |
| `analysis` | RSI, MACD, ATR, VWAP, Bollinger; SMC (BOS, CHoCH, OB, FVG); Elliott; MLSignal | Pure computation |
| `research` | Macro (rates, DXY, PMI), on-chain (MVRV, funding, OI), DeFi yields, sentiment | I/O — external APIs |
| `reporting` | Strategy report (markdown/PDF), Pine Script v6 export, backtest diagnostics | Computation → artifact |
| `execution` | Order helpers — size calculators, SL/TP builders, position sizing | Pure computation (no exchange calls) |

> **Important:** Vibe Trading's `execution` skills are _helpers_, not executors.
> They are used internally by operator COMPUTE nodes.
> Actual exchange calls go through the MCP server or the operator's own EXECUTE nodes.

---

## The 3-Layer Call Stack

```
MotisAgentLoop
     │  calls tool by name (e.g. "data.ohlcv")
     ▼
MotisToolRouter.dispatch()
     │  routes — is it a finance skill? memory? web? MCP?
     ▼
run_finance_skill(tool_name, args, ctx)
     │  dispatches to the actual function
     ▼
Skill implementation (e.g. get_ohlcv_ccxt, detect_bos, analyze_macro)
```

The same `call_skill()` function is used by both:
- The **master agent** (via `MotisToolRouter`)
- **Operator nodes** (via `motis_operator.sdk.call_skill`)

This means a skill ported once works in both contexts.

---

## Naming Convention

Tool names use `category.skill` dot notation:

| Tool Name | Handler | Vibe Trading Source |
|---|---|---|
| `data.ohlcv` | `route_data_source()` | `data/routing.py` |
| `smc.structure` | `detect_bos()` + `detect_choch()` + `detect_fvg()` | `analysis/smc.py` |
| `technical.indicators` | `calc_rsi()`, `calc_macd()`, etc. | `analysis/technical.py` |
| `research.macro` | `analyze_macro_environment()` | `research/macro.py` |
| `research.onchain` | `get_onchain_metrics()` | `research/onchain.py` |
| `research.fundamentals` | `get_financial_statements()` | `research/fundamentals.py` |
| `report.generate` | `generate_strategy_report()` | `reporting/report_generate.py` |
| `report.pine_script` | `export_pine_script()` | `reporting/pine_script.py` |

> The agent never calls Vibe Trading functions directly — always through the router.
> This lets us add caching, rate limiting, error normalisation, and feature flags
> in one place without touching the skill implementations.

---

## What the Agent Sees

The agent sees these as just another set of tools alongside `web_search`, `terminal`,
`memory_add`, etc. From its perspective, there is no "Vibe Trading" — there are just tools
it can call.

This is intentional: it means we can swap or augment the skill implementations later
(e.g., replace ccxt with a custom exchange client) without changing the agent loop or prompts.

---

## Porting Guide: Copy-Paste Ratios

| Component | Copy-paste % | What changes |
|---|---|---|
| `example_signal_engine.py` files | ~85% | Import path, wrap in `run_finance_skill()` handler |
| `SKILL.md` content | 100% | Becomes context block / system prompt injection |
| `tools/pattern_tool.py` | ~90% | Add to tool router, minor imports |
| `tools/factor_analysis_tool.py` | ~90% | Add to tool router |
| `tools/options_pricing_tool.py` | ~90% | Add to tool router |
| Swarm YAML configs | 0% runnable | Use as operator design templates only |
| Backtest engines + loaders + metrics | ~70% | Go in `services/platform/`, minor adapter |
| `backtest/runner.py` | ~40% | Rewrite to integrate with BacktestOperator lifecycle |
| Agent core (`src/agent/`) | 0% | Superseded by Hermes-based MotisAgentLoop |

---

## Implementation Backlog

### Phase 1 — Core data + analysis (unlocks 80% of agent utility)
Zero external API dependencies — just ccxt/yfinance/pandas.

| Priority | Tool | Target file | External dep |
|---|---|---|---|
| 1 | `data.ohlcv` | `skills/finance/data/routing.py` | ccxt / yfinance |
| 2 | `smc.structure` | `skills/finance/analysis/smc.py` | pandas-ta |
| 3 | `technical.indicators` | `skills/finance/analysis/technical.py` | ta / pandas-ta |

### Phase 2 — Research (needs external APIs)

| Priority | Tool | Target file | External dep / key |
|---|---|---|---|
| 4 | `research.onchain` | `skills/finance/research/onchain.py` | Coinglass / Glassnode API |
| 5 | `research.macro` | `skills/finance/research/macro.py` | FRED API / yfinance |
| 6 | `research.fundamentals` | `skills/finance/research/fundamentals.py` | yfinance / Alpha Vantage |

### Phase 3 — Reporting (high value for operators + marketplace)

| Priority | Tool | Target file | External dep |
|---|---|---|---|
| 7 | `report.generate` | `skills/finance/reporting/report_generate.py` | matplotlib / jinja2 |
| 8 | `report.pine_script` | `skills/finance/reporting/pine_script.py` | None |

---

## What Does NOT Become an Agent Tool

These Vibe Trading categories are used internally but **not** exposed to the master agent:

| Category | Reason | Used by |
|---|---|---|
| `execution` (SL/TP, sizing helpers) | Internal to operator COMPUTE nodes | `packages/operator_sdk/` |
| Backtest runner | Heavy compute, long-running | BacktestOperator |
| Live trade submission | Goes through operator EXECUTE nodes | Operator's `submit_order()` |

---

## SkillRegistry Role

`SkillRegistry` is the façade. It currently returns `FINANCE_SKILL_DEFINITIONS`.
Future evolution:

1. Filter skills by user subscription tier (free vs. pro)
2. Include user-uploaded custom skills
3. Cache tool schema lists per user (instant loop startup)

The registry does **not** do dispatch — that's `run_finance_skill()` + `MotisToolRouter`.

---

## Upstream Reference

The Vibe Trading source is vendored at `services/agent/upstream/vibe_trading/` with
a `MOTIS_PORTING_NOTES.md` guide. Same pattern as the Hermes vendor at
`services/agent/upstream/hermes/`.

---

## Code Flow Summary

```
Vibe Trading skills → finance/__init__.py → FINANCE_SKILL_DEFINITIONS
                                         → run_finance_skill() dispatcher
                                               ↓
UserContext.skill_registry.get_tool_definitions()  ← SkillRegistry reads from ^
                                               ↓
MotisAgentLoop._build_tools()  — includes these in the OpenAI tool list
                                               ↓
MotisToolRouter._dispatch_native()  — routes "data.*" / "smc.*" / "technical.*" calls
                                               ↓
Actual skill function execution (ported from Vibe Trading)
```
