# Motis — Product Requirements Document (PRD)
**Version:** 0.4 — Agent/Operator separation + Hermes sub-agent system  
**Date:** 2026-04-10  
**Status:** Draft for review

> **Changelog v0.4:** Clarified the boundary between the Master Agent and Operators. SwarmRunner moves from being an inline agent skill to the engine inside `ResearchOperator` (a standalone, persistent, schedulable Operator). The Master Agent gains two Hermes-sourced tools: `SubagentRunner` (adapted from `delegate_tool`) for general-purpose parallel task delegation, and `MixtureOfAgents` (adapted from `mixture_of_agents_tool`) for hard multi-model reasoning. Agents working on this project should treat this version as the definitive design.

> **Changelog v0.2:** Vibe-Trading integration strategy changed from "external MCP sidecar" to "absorbed in-process library." Its 68 finance skills become native Motis skills; 29 swarm presets become native SwarmRunner presets; backtest engine imported as a library. This eliminates one service from the deployment stack and gives full control over customization.

---

## Table of Contents
1. [Vision & Positioning](#1-vision--positioning)
2. [User Personas](#2-user-personas)
3. [Core Concepts & Glossary](#3-core-concepts--glossary)
4. [User Journeys](#4-user-journeys)
5. [Product Areas](#5-product-areas)
   - 5.1 Motis Master Agent
   - 5.2 The Operator
   - 5.3 Operator Builder
   - 5.4 Research & Backtesting
   - 5.5 Paper Trade & Live Trade
   - 5.6 The Arena
   - 5.7 Operator Marketplace
   - 5.8 Platform Frontend
   - 5.9 Gateway (Messaging)
6. [Technical Architecture](#6-technical-architecture)
   - 6.1 System Overview
   - 6.2 Component Details
   - 6.3 Model Layer (BYOM)
   - 6.4 Scaling Strategy
7. [Infrastructure Requirements](#7-infrastructure-requirements)
8. [Data Model (Conceptual)](#8-data-model-conceptual)
9. [Open Questions & Risks](#9-open-questions--risks)
10. [Phased Build Roadmap](#10-phased-build-roadmap)

---

## 1. Vision & Positioning

### 1.1 The Problem

Agentic AI traders fail in practice for two opposite reasons:
- **Pure LLM agents** (OpenClaw-style) are too non-deterministic for live trading — models "reason" their way into bad trades, miss timing constraints, and can't be audited.
- **Traditional bots** (3Commas, Pionex) are deterministic but dumb — no natural language interface, no research loop, no adaptability.

The deeper problem: getting from "I have a trading idea" to "I have a running, verified, live strategy" requires expertise across research, backtesting, risk management, and exchange integration — a stack that doesn't exist in one unified product.

### 1.2 The Solution — Motis

Motis is an **agentic trading platform** where a conversational AI coordinator helps users research, build, validate, and deploy **Operators** — deterministic but agentic trading workflows that run autonomously on their behalf.

The platform loop:
```
Idea ──► Research ──► Backtest ──► Paper Trade ──► Live Operator
  ▲                                                      │
  └──────────── Agent-assisted refinement ◄──────────────┘
```

### 1.3 Competitive Positioning

| Platform | Approach | Key Gap |
|---|---|---|
| Vibe-Trading | ReAct agent + research skills | No persistent operators, no live trading, no platform |
| Hermes | General self-improving agent | No finance domain, no operators, no web platform |
| 3Commas / Pionex | Pre-built bots | Code-first, no NL, no research loop, no AI |
| QuantConnect | Full quant platform | Code-only, no NL, no AI-built strategies |
| **Motis** | NL coordinator → verified operators → live deployment + competition + marketplace | End-to-end, unified |

### 1.4 The Moat

1. **Operator quality** — Operators are built through a research-backtest-papertrade verification loop, not just deployed blindly.
2. **Platform-verified performance** — All marketplace operators have immutable live trade records. No self-reported stats.
3. **Competition network effects** — The Arena creates a talent discovery and performance ranking system that compounds over time.
4. **Model agnosticism** — Users bring their own models (BYOM); future partnerships with model providers will enable co-marketing and fine-tuned trading models.

---

## 2. User Personas

### 2.1 The Retail Trader ("Alex")
- **Background:** Active crypto/equities trader, understands markets, no coding skills
- **Goal:** Automate their strategy without learning to code
- **Journey:** Describes idea in chat → agent builds an Operator → deploys it → monitors performance
- **Engages with:** Chat, Operators sidebar, Arena (discovery), Marketplace (buying)

### 2.2 The Quant / Developer ("Morgan")
- **Background:** Quantitative background, comfortable with Python and market data
- **Goal:** Rapidly iterate on strategies using AI research tools; sell verified strategies
- **Journey:** Uses research swarms to generate ideas, backtests rigorously, deploys operators, sells on Marketplace
- **Engages with:** All features; deep backtest analytics, operator source editing, Marketplace publishing

### 2.3 The Follower ("Jordan")
- **Background:** Interested in automated trading, doesn't want to build their own strategies
- **Goal:** Subscribe to proven operators and let them trade autonomously
- **Journey:** Browses Marketplace → subscribes to top-ranked, platform-verified operators → monitors their account
- **Engages with:** Marketplace, passive portfolio view

### 2.4 The Competitor ("Sam")
- **Background:** Confident in their operator's performance, wants recognition and discovery
- **Goal:** Win Arena competitions, build reputation, attract marketplace subscribers
- **Journey:** Enters AUM-class Arena → competes live → leaderboard drives marketplace discovery
- **Engages with:** Arena, Marketplace publishing, chat for refinement

---

## 3. Core Concepts & Glossary

| Term | Definition |
|---|---|
| **Master Agent** | The conversational AI coordinator. Powered by a Hermes-based multi-user agent. Understands the user's goals, manages their operators, and orchestrates research/backtest/build workflows. |
| **Operator** | A deterministic, agentic trading workflow built with LangGraph. Each Operator is a full trading strategy — it manages signals, risk, execution, and monitoring across one or more assets. Model reasoning is used only at specific decision nodes inside the workflow. |
| **Skill** | A lightweight, one-shot capability (Python function or MCP tool call) that Operators and the Master Agent can invoke. Examples: `fetch_ohlcv`, `calc_rsi`, `detect_bos`. The agent ships with 68+ native finance skills (absorbed from Vibe-Trading) across 7 categories: data, analysis, research, reporting, execution, and builtin. New skills can be created by the agent from conversation. |
| **Research Swarm** | A multi-agent debate team built as a native LangGraph multi-agent graph. Comes with 29 preset team configurations (crypto trading desk, investment committee, quant strategy desk, etc.). Each agent in a swarm plays a specific role (bull analyst, bear analyst, quant, macro, risk officer) and their outputs are synthesized into a research brief. |
| **Operator Builder** | The workflow within the Master Agent that translates a user's strategy conversation into a deployable Operator definition. |
| **Paper Trade** | Simulated execution using real market data but no real capital. Used to validate an Operator before going live. |
| **Live Trade** | Real execution against a connected exchange account using user-supplied API keys. |
| **Arena** | A live trading competition where Operators compete within AUM weight classes. Each Operator trades in its own account; the platform ranks by standardized performance metrics. |
| **AUM Class** | The arena weight class, defined by the Operator's deployed capital (e.g., Nano: <$1k, Micro: $1k–$10k, Small: $10k–$100k, etc.). |
| **Marketplace** | A store where users can publish or subscribe to Operators. All performance data is platform-verified from live trade history. |
| **Operator Spec** | The serialized definition of an Operator (LangGraph graph definition, parameters, risk config, asset universe). Excludes API keys. |
| **BYOM** | Bring Your Own Model. Users can configure any OpenAI-compatible model endpoint for the Master Agent and/or their Operators. |

---

## 4. User Journeys

### 4.1 Journey A — "Build and Deploy an Operator" (Alex / Morgan)

```
1. User opens Motis → lands on chat interface
2. User: "I want to trade BTC perps using funding rate arbitrage with tight risk controls"
3. Master Agent:
   a. Recognizes this as a strategy request
   b. Invokes ResearchSwarm → generates market analysis + strategy thesis
   c. Streams research output to chat
   d. Proposes an Operator structure (graph nodes, risk parameters)
4. User reviews, adjusts parameters in conversation
5. Agent builds Operator spec → displays it in sidebar as "Draft"
6. User: "Backtest this on the last 6 months"
7. Agent invokes BacktestOperator → runs Vibe-Trading backtest engine
8. Results shown in chat (Sharpe, max DD, win rate) + link to full report
9. User: "Looks good, paper trade it for a week"
10. Agent activates PaperTradeOperator → appears in sidebar as "Running (Paper)"
11. After one week, user reviews paper trade summary
12. User: "Deploy it live on Hyperliquid with $5k"
13. Agent prompts for Hyperliquid API key (if not set) → activates LiveTradeOperator
14. Operator appears in sidebar as "Live 🟢" with real-time P&L
```

### 4.2 Journey B — "Enter the Arena" (Sam)

```
1. User has a live Operator running with $8,000 AUM
2. User navigates to Arena (header)
3. Arena shows available competitions: "Micro Class ($1k–$10k) — Crypto Perps — 30 days"
4. User enters with their Operator → Operator's live account is registered for scoring
5. Platform begins tracking performance relative to other entrants (same AUM class)
6. Leaderboard updates in real-time (daily snapshots for ranking)
7. At competition end, platform publishes verified results
8. User's Operator appears on Marketplace with a "Top 3 — Micro Arena, April 2026" badge
```

### 4.3 Journey C — "Subscribe to an Operator" (Jordan)

```
1. User opens Marketplace (header)
2. Browses filters: Asset Class, AUM Class, Strategy Style, Verified Return, Drawdown
3. Selects "BTC Funding Rate Arb" — 18% annualized, 4.2% max DD, Sharpe 2.1
4. Views: platform-verified live trade history, Arena performance, operator description
5. Subscribes ($29/month)
6. Platform instantiates the Operator spec in Jordan's account with Jordan's own exchange keys
7. Operator runs autonomously, Jordan monitors P&L in their sidebar
```

---

## 5. Product Areas

### 5.1 Motis Master Agent

**What it is:** A multi-user, web-hosted adaptation of Hermes Agent. The primary conversational interface for everything in the platform.

**Capabilities:**
- Long-term per-user memory (strategy history, risk preferences, connected exchanges, past conversations)
- Knows about the user's registered Skills and Operators — can list, explain, invoke, or modify them
- Routes user requests into the right workflow: research → backtest → build → paper trade → live deploy
- Streams all agent loop steps explicitly to the frontend (tool calls, thinking, intermediate results) — user sees exactly what the agent is doing
- Supports BYOM: user can configure any OpenAI-compatible endpoint for the master agent itself
- Supports multi-turn strategy refinement
- **Sub-agent delegation:** spawns N concurrent child agent loops for parallel independent tasks
- **Mixture-of-Agents:** routes hard analytical problems through multiple frontier models and synthesizes results

**Tool registry — what the Master Agent can call:**

| Tool | Source | Purpose |
|---|---|---|
| `finance.*` (68 skills) | Vibe-Trading (absorbed) | Data, SMC analysis, technical indicators, reporting |
| `operator_*` | Motis operator layer | CRUD + invoke operators (create, list, status, archive) |
| `execute_paper_trade`, `execute_live_trade` | Motis MCP | Trading execution (risk guard enforced at MCP layer) |
| `web_search`, `web_fetch` | Hermes `web_tools.py` | Research, news, financial reports, SEC filings |
| `terminal` (sandboxed) | Hermes `terminal_tool.py` | Run Python analysis scripts in isolated container |
| `memory_*` | Hermes `memory_tool.py` (adapted) | DB-backed per-user memory (replaces filesystem) |
| `delegate_task` | Hermes `delegate_tool.py` (adapted) | Spawn N parallel sub-agent loops for independent tasks |
| `mixture_of_agents` | Hermes `mixture_of_agents_tool.py` (adapted) | Route hard problems through multiple frontier models |

**What the Master Agent does NOT do inline:**
- Run research swarms → creates/invokes a `ResearchOperator` instead (persisted, visible in sidebar)
- Run backtests → creates/invokes a `BacktestOperator` instead (persisted, results attached to Operator spec)
- Execute live trades directly → always routed through the MCP execution layer with risk guard

**Technical foundation — Hermes files adapted for Motis:**

| Hermes file | Motis adaptation | Key changes |
|---|---|---|
| `run_agent.py` → `AIAgent` class | `core/loop.py` → `MotisAgentLoop` | Remove FS state; inject `UserContext`; yield SSE events instead of print |
| `agent/context_compressor.py` | `core/compression.py` | Take as-is — critical for long trading sessions |
| `agent/memory_manager.py` | `core/memory.py` | Replace SQLite/file with PostgreSQL FTS; scope queries to `user_id` |
| `agent/prompt_builder.py` | `core/prompts.py` | Update identity, platform hints, skill guidance for Motis |
| `tools/delegate_tool.py` | `tools/subagent.py` | Replace `AIAgent` spawn with `MotisAgentLoop` spawn; remove Docker/Modal backends; share `UserContext` |
| `tools/mixture_of_agents_tool.py` | `tools/moa.py` | Replace OpenRouter hardcoded models with user's BYOM config; make async-native |
| `tools/web_tools.py` | `tools/web.py` | Take as-is; add Brave/Tavily key from user's `UserContext` config |
| `tools/terminal_tool.py` | `tools/terminal.py` | Harden sandbox: per-user Docker container, no network, 30s timeout, import restrictions |
| `model_tools.py` | `core/model.py` | OpenAI-compatible LLM calling; replace Hermes provider router with simpler BYOM config |
| `trajectory_compressor.py` | `core/trajectory.py` | Take as-is |

> **Hermes upstream is at:** `services/agent/upstream/hermes_agent/`. Do not edit it. Copy files to `services/agent/motis_agent/` and adapt there.

---

### 5.2 The Operator

**What it is:** A full trading strategy implemented as a LangGraph `StateGraph`. It manages an asset universe (can be multi-asset), generates signals, enforces risk rules, and executes trades either in paper mode or against a live exchange.

**Structure:**
```python
# Conceptual node structure for a LiveTradeOperator
class OperatorState(TypedDict):
    market_data: dict          # OHLCV, orderbook, funding rates
    signals: list[Signal]      # Generated trade signals
    risk_assessment: RiskResult
    pending_orders: list[Order]
    positions: list[Position]
    run_log: list[str]

graph = StateGraph(OperatorState)
graph.add_node("fetch_market_data", fetch_market_data_node)      # deterministic
graph.add_node("generate_signals", generate_signals_node)         # model reasoning here
graph.add_node("risk_check", risk_check_node)                     # deterministic rules
graph.add_node("user_approval", user_approval_node)               # optional HITL
graph.add_node("execute_orders", execute_orders_node)             # deterministic
graph.add_node("monitor_positions", monitor_positions_node)       # deterministic
```

**Operator types:**

| Type | What it does | Trigger |
|---|---|---|
| `LiveTradeOperator` | Runs a live strategy against an exchange | Time-based or event-based |
| `PaperTradeOperator` | Same as live but simulated fills | Time-based or event-based |
| `BacktestOperator` | Runs strategy against historical data; produces metrics + report | On-demand (ad hoc) |
| `ResearchOperator` | Runs a multi-agent research swarm; persists the brief | Scheduled or on-demand |

**ResearchOperator** is a first-class Operator type, not an inline agent skill. It wraps `SwarmRunner` in a LangGraph graph with persistence, scheduling, and sidebar visibility:

```python
# ResearchOperator node structure
class ResearchState(TypedDict):
    prompt: str
    swarm_preset: str              # e.g. "crypto_trading_desk"
    per_agent_outputs: dict        # bull, bear, quant, macro, risk
    synthesis: str                 # final brief
    report_url: str                # S3 link to full report

graph = StateGraph(ResearchState)
graph.add_node("configure_swarm", configure_swarm_node)    # pick preset + inject market context
graph.add_node("run_swarm_agents", run_swarm_agents_node)  # SwarmRunner.stream() — parallel model calls
graph.add_node("synthesize", synthesize_node)              # model call: synthesize all agent outputs
graph.add_node("persist_brief", persist_brief_node)        # save to S3 + trade_context table
graph.add_node("notify_user", notify_user_node)            # SSE event: "Research complete"
```

This means:
- Research results are **persisted** — user reviews the full brief in the sidebar days later
- Research can be **scheduled** — e.g., "run BTC macro brief every Sunday at 00:00"
- Research briefs can **feed other operators** — a `LiveTradeOperator` reads the latest brief from the `trade_context` table as signal context
- Research brief is **attached to backtest specs** — marketplace listings show the research thesis alongside verified performance

**Operator states:**
- `draft` — built, not yet backtested
- `backtested` — has backtest results attached
- `paper` — actively paper trading
- `live` — actively live trading
- `paused` — manually paused
- `archived` — inactive
- `complete` — for `BacktestOperator` and `ResearchOperator` on-demand runs

---

### 5.3 Operator Builder

**What it is:** The workflow inside the Master Agent that translates a strategy conversation into a deployable Operator spec.

**Modes:**
1. **Agent-driven:** User describes a strategy in natural language. The agent: generates a research thesis (optional), proposes an operator graph structure, writes the LangGraph nodes, sets default risk parameters. User reviews and approves.
2. **User-defined:** Power user (Morgan) can edit operator node code directly in the platform. The agent assists with code generation, debugging, and optimization suggestions.
3. **Marketplace instantiation:** When subscribing to a marketplace operator, the operator spec is cloned and parameterized (exchange keys, risk limits, capital allocation) for the subscribing user.

**Conversation-to-Operator flow:**
```
User describes strategy
  ↓
Agent asks clarifying questions (asset universe? timeframe? risk tolerance?
  existing strategy code to adapt?)
  ↓
Agent creates a ResearchOperator (optional, user can skip)
  ↓ ResearchOperator runs async — user sees "Research running..." in sidebar
Agent proposes operator graph + parameters in structured form
  ↓
User approves or refines in conversation
  ↓
Operator spec written to DB → appears in sidebar as "Draft"
  ↓
Agent recommends next step (backtest / paper trade)
```

> **Key principle:** The Master Agent never runs a swarm inline. It always creates a `ResearchOperator` so the results are persisted, schedulable, and referenceable by other operators.

---

### 5.4 Research & Backtesting

**Research — via `ResearchOperator`:**
- Research is always run as a `ResearchOperator`, never inline in the agent loop
- Agent creates a `ResearchOperator` referencing the chosen preset and invokes it via `operator_invoke`
- Available presets (29 total): `investment_committee`, `crypto_trading_desk`, `quant_strategy_desk`, `macro_rates_fx_desk`, etc.
- Each agent role (bull, bear, quant, macro, risk) runs as a separate model call inside `SwarmRunner`; results are synthesized
- Output streamed to chat in real-time via SSE (per-agent role events as they complete)
- Results persisted to DB + S3; visible as a completed operator run in the sidebar
- ResearchOperators can be scheduled (e.g., weekly macro brief), not just one-shot
- Research brief is scoped to the user and can be read by their `LiveTradeOperator` as signal context

**Research vs. Sub-agent delegation — when to use which:**

| Need | Use |
|---|---|
| "Analyze BTC from bull/bear/quant/macro perspectives" | `ResearchOperator` (structured domain expert debate, persisted) |
| "Do X and Y in parallel right now" | `delegate_task` (Hermes sub-agent, ephemeral, general-purpose) |
| "Solve this hard analytical problem" | `mixture_of_agents` (multi-model reasoning, ephemeral) |

**Backtesting:**
- Always runs as a `BacktestOperator` (persisted, results attached to Operator spec)
- Data routing via native auto-fallback skill: 5 sources (ccxt, yfinance, akshare, tushare, okx) with zero-config for most markets
- Supported markets: crypto (CCXT, OKX), US/HK equities (yfinance), A-shares (tushare/AKShare), forex, futures
- Output: Sharpe ratio, max drawdown, win rate, Calmar, full trade log, equity curve
- Pine Script v6 export → user can visualize on TradingView
- **Backtest results are attached to the Operator spec** — displayed in sidebar and referenced in Marketplace listings
- `BacktestOperator` node structure: `strategy_parse → data_fetch → engine_run → metrics → ai_critique → persist_report`
  - The `ai_critique` node uses a model to identify failure modes and suggest improvements

> **Implementation note:** Vibe-Trading's codebase (MIT licensed) was the source for the 68 skills, 29 swarm presets, and backtest engine. They are maintained in the Motis repo. Attribution preserved per MIT terms.

---

### 5.5 Paper Trade & Live Trade

**Paper Trade:**
- Operator runs against real market data, simulated fills using mid-price + configurable slippage model
- No real capital at risk
- Full position tracking, P&L, trade log in sidebar
- Runs on the same Operator code path as live — only the execution MCP tool changes (`paper_trade` vs `live_trade`)
- Can run indefinitely or for a fixed duration set by the user

**Live Trade:**
- Requires user to connect an exchange API key (stored encrypted, never exposed to the Operator code — injected at the execution MCP layer)
- Initial supported exchanges: Hyperliquid, Binance (already built in the existing project)
- Expanded via CCXT for 100+ exchanges
- Two-layer risk enforcement:
  - **Operator layer:** User/agent-defined risk rules (stop-loss, position sizing, daily loss limit per strategy)
  - **Platform layer:** Hard caps set per-user account (max leverage, max single-position size, global daily loss kill-switch). Platform layer cannot be overridden by operator code.
- Explicit agent loop messages streamed to frontend — user can see every decision the operator makes in real-time

---

### 5.6 The Arena

**Concept:** A live trading competition where Operators trade in their own accounts (no shared sandbox) and are ranked by standardized performance metrics within AUM weight classes.

**AUM Weight Classes:**
| Class | Deployed Capital | 
|---|---|
| Nano | < $1,000 |
| Micro | $1,000 – $10,000 |
| Small | $10,000 – $100,000 |
| Medium | $100,000 – $1,000,000 |
| Large | > $1,000,000 |

**Competition Structure:**
- Each competition has: name, AUM class, duration (e.g., 7-day, 30-day, 90-day), eligible asset/exchange categories (optional — can be open to any market), scoring metric (primary: risk-adjusted return / Sharpe; secondary: total return)
- Users register their live Operator with its existing exchange account — the Operator keeps trading exactly as it was; the Arena layer reads performance snapshots from the platform's verified trade log
- Multiple competitions can run simultaneously across different AUM classes and asset categories
- An Operator can be registered in at most one competition at a time per deployment

**Ranking & Scoring:**
- Performance is pulled from the platform's verified live trade record (same source used for Marketplace)
- Scoring: Sharpe ratio (primary) + total return (secondary) over the competition window, starting from registration date
- Leaderboard updates daily (to prevent HFT-style gaming of intraday snapshots)
- Final results published and permanently attached to the Operator's performance record

**Arena Infrastructure:**
- The platform does NOT run a shared market or clearing house — each participant's Operator trades independently on their own exchange accounts
- Platform reads results from verified trade logs (pulled from connected exchange accounts at regular intervals, cross-referenced with exchange API history)
- Leaderboard served via WebSocket for real-time feel; underlying data refreshes daily
- Anti-gaming: API-verified trade history (platform calls the exchange API directly to verify positions and fills — not self-reported). Operators that disconnect from the exchange during the competition period are flagged.

**Post-Competition:**
- Results badge generated (e.g., "🥇 Micro Class, BTC Arena, April 2026")
- Badge is permanently displayed on the Operator's Marketplace listing
- Operators with top-3 finishes are featured in a discovery section of the Marketplace

---

### 5.7 Operator Marketplace

**Concept:** A store where users publish Operators with platform-verified live performance. Subscribers get the Operator instantiated in their own account with their own exchange credentials.

**Discovery & Filtering:**
- Filters: Asset class, strategy style (trend/arb/market-neutral/etc.), AUM class, verified return period, max drawdown, Sharpe, Arena badges, subscription price
- Algorithm-ranked feed (recency + Sharpe + Arena wins + subscriber count)
- Comparable to TradingView's Pine Script marketplace but for live, verified, agentic operators

**Operator Listing Requirements (to publish):**
- Minimum 30 days of verified live trade history on the platform
- Operator must currently be live (or have been live within the last 60 days)
- Publisher must pass basic KYC / identity verification
- Platform verifies trade history by calling exchange APIs directly — cross-referenced with Operator's internal run log
- Performance stats are calculated by the platform, not self-reported

**Performance Verification:**
- Platform maintains an immutable, timestamped record of every trade executed by every live Operator (pulled from exchange fill confirmations)
- When an Operator is listed, the platform publishes: verified total return, Sharpe, max drawdown, win rate, trade count, holding period distribution — all with "Verified by Motis" badge
- Auditable: subscribers can see the actual trade log (entry price, exit price, size, timestamp) — no PnL manipulation possible

**Subscription Model:**
- Publisher sets a monthly subscription price (platform takes a cut, e.g., 20%)
- On subscription: Operator spec is cloned into subscriber's account, exchange API key slots are mapped to subscriber's connected exchange
- Operator runs independently in subscriber's account — publisher cannot access subscriber funds or keys
- If publisher updates the Operator (new version), subscribers are notified and can opt in to the update or stay on the current version
- Subscriber can pause/cancel at any time; Operator stops trading on next tick after cancellation

**Publishing Flow:**
```
User requests to publish Operator
  ↓
Platform checks: ≥30 days verified live history? ✓
  ↓
Platform computes verified performance stats
  ↓
User writes listing description (agent can help draft it)
  ↓
User sets subscription price
  ↓
Platform review (automated checks + optional manual spot-check)
  ↓
Listing goes live → appears in Marketplace
```

---

### 5.8 Platform Frontend

**Framework:** Next.js (SSR for Marketplace SEO, App Router for dynamic sections)

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  HEADER: [Motis Logo]    [Arena]  [Marketplace]  [Account]  │
├───────────────┬─────────────────────────────────────────────┤
│               │                                             │
│  SIDEBAR      │            MAIN: CHAT                       │
│               │                                             │
│  My Operators │  ┌─────────────────────────────────────┐   │
│  ──────────── │  │ Agent Loop Stream                   │   │
│  🟢 BTC Arb   │  │ (tool calls, thinking, results      │   │
│  $5,234 +2.1% │  │  visible in expandable blocks)      │   │
│               │  ├─────────────────────────────────────┤   │
│  📄 ETH Trend │  │                                     │   │
│  Backtested   │  │        Conversation History         │   │
│               │  │                                     │   │
│  [+ New]      │  ├─────────────────────────────────────┤   │
│               │  │ [Type a message...]          [Send] │   │
│               │  └─────────────────────────────────────┘   │
└───────────────┴─────────────────────────────────────────────┘
```

**Key UI Components:**

**Chat (Main Area):**
- Streaming agent messages with explicit tool call display (expandable)
- Rich message types: research summaries, backtest reports, operator proposals (with approve/edit actions), trade notifications
- Persistent conversation history per user

**Operators Sidebar:**
- Card per operator: name, state badge, key metric (P&L % for live, Sharpe for backtested), quick actions
- Click → expanded operator detail view (full graph visualization, trade log, settings)
- Operator state machine visible and actionable (pause, edit, archive, enter Arena, publish to Marketplace)

**Arena Page:**
- Active competitions browser (filter by AUM class, asset category, duration)
- Competition detail: current leaderboard, time remaining, your operator's rank (if entered)
- Past competitions with final results
- "Enter Competition" flow (requires live operator in the relevant AUM class)

**Marketplace Page:**
- Discovery feed with filters
- Operator listing detail: verified performance chart, trade log viewer, strategy description (auto-drafted by agent, reviewed by publisher), Arena badges
- Subscribe flow: confirm subscription, map exchange credentials

**Account / Settings:**
- Connected exchanges (API key management, encrypted)
- Model configuration (BYOM endpoint, API key)
- Platform-level risk limits
- Subscription management (active marketplace subscriptions, own published operators)
- Billing

---

### 5.9 Gateway (Messaging)

**Foundation:** Hermes Gateway (supports Telegram, Discord, Slack, WhatsApp, Signal, Email)

**Scope for V1:** Preserve the gateway but treat it as a secondary interface. Users can receive trade notifications, ask their Master Agent questions, and get Operator status updates via Telegram or Discord.

**Future:** Full operator management via messaging (pause, resume, get reports). Deep-dive design in a later phase.

---

## 6. Technical Architecture

> **For agents reading this PRD:** The platform has two distinct runtime tiers with completely different scaling strategies. Do not conflate them — they have different latency requirements, state models, and failure modes. The conversation layer is stateless and horizontally scalable. The operator layer is stateful, event-driven, and requires durable execution guarantees.

### 6.1 Two-Speed System Design

Motis runs two fundamentally different workloads simultaneously:

| | Conversation Layer | Operator Layer |
|---|---|---|
| **Unit** | Chat request / SSE stream | Operator tick (scheduled or event-triggered) |
| **State model** | Stateless per-request (state in DB) | Stateful across ticks (checkpoint in Redis + DB) |
| **Latency requirement** | < 2s to first token | Sub-second after candle close |
| **Scaling mechanism** | Horizontal pod scaling | Event-driven fan-out + worker pool |
| **Failure model** | Retry request | Durable workflow — survives worker crash |
| **Phase 0 implementation** | FastAPI + SSE | Celery + Redis |
| **Production implementation** | FastAPI pods behind LB | Kafka fan-out + Temporal workers |

### 6.2 System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MOTIS PLATFORM                               │
│                                                                      │
│  ══════════════════ CONVERSATION LAYER (stateless) ════════════════  │
│                                                                      │
│  ┌──────────┐   ┌──────────────────────────────────────────────┐   │
│  │ Next.js  │   │         API Gateway (FastAPI pods)            │   │
│  │ (CDN)    │◄─►│  Auth · Rate Limit · Router · SSE proxy       │   │
│  └──────────┘   └───────────────────┬──────────────────────────┘   │
│                                      │                               │
│               ┌──────────────────────▼──────────────────────┐       │
│               │    Agent Service (Hermes fork, N pods)        │       │
│               │  Stateless per-request. State in DB+Redis.    │       │
│               │  68 finance skills + 29 swarms in-process.    │       │
│               └──────────────────────┬──────────────────────┘       │
│                                      │ MCP                           │
│               ┌──────────────────────▼──────────────────────┐       │
│               │           Motis MCP Server                    │       │
│               │  Trading Exec (risk guard) only               │       │
│               └──────────────────────────────────────────────┘       │
│                                                                      │
│  ═══════════════════ OPERATOR LAYER (event-driven) ════════════════  │
│                                                                      │
│  ┌─────────────────────────┐   ┌──────────────────────────────┐    │
│  │  Market Data Bus         │   │  Operator Dispatcher          │    │
│  │  (Phase 0: polling)      │──►│  Determines which operators   │    │
│  │  (Phase 2+: Kafka/       │   │  react to each market event   │    │
│  │   Redpanda WS fan-out)   │   └──────────────┬───────────────┘    │
│  └─────────────────────────┘                  │                     │
│                                                │                     │
│  ┌─────────────────────────────────────────────▼─────────────────┐  │
│  │              Operator Runtime                                   │  │
│  │  Phase 0–1:  Celery workers + Beat scheduler                    │  │
│  │  Phase 2+:   Temporal.io workers (durable, dedup, replay)       │  │
│  │                                                                  │  │
│  │  Each operator tick: restore state → run LangGraph → checkpoint  │  │
│  └──────────────────────────────┬────────────────────────────────┘  │
│                                  │                                   │
│  ┌───────────────────────────────▼────────────────────────────────┐ │
│  │              Exchange Gateway (per exchange)                     │ │
│  │  Rate limit mgmt · Order dedup key · Fill reconciler            │ │
│  │  AES-256 key injection · Audit log writer                       │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ══════════════════════════ DATA LAYER ═══════════════════════════  │
│  PostgreSQL · Redis · S3/R2 · (Phase 2+: Kafka for market events)   │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Component Details

#### Agent Service (Hermes Fork) — Conversation Layer
- Horizontally scalable: N stateless pods behind a load balancer
- Each HTTP request carries a JWT → resolves to a `UserContext` scoped to that user
- `UserContext` wraps: memory store (PostgreSQL), skill registry, operator registry, conversation session (Redis-cached, DB-persisted)
- Agent loop is **stateless per-request**: context loaded from DB at request start, saved at end. Any pod can handle any user
- SSE streams are pinned to a pod via sticky sessions or a Redis pub/sub relay
- Model calls go to the user's configured BYOM endpoint, or platform default

#### Market Data Bus — Operator Layer
- **Phase 0–1:** Each operator polls its required symbols independently via the native data routing skill
- **Phase 2+:** Kafka/Redpanda as a shared market data bus
  - One WebSocket connection per (symbol, timeframe, exchange) feeds ALL operators watching that symbol
  - Topics: `candles.{exchange}.{symbol}.{timeframe}`, `orderbook.{exchange}.{symbol}`, `funding.{exchange}.{symbol}`
  - This is O(symbols) connections, not O(operators) — critical at scale
  - Operator Dispatcher subscribes to topics and determines which operators to trigger on each event

#### Operator Runtime — Operator Layer
- **Phase 0–1 (Celery):**
  - Celery Beat schedules per-operator tasks based on `trigger_config.interval_seconds`
  - Workers restore LangGraph state from Redis, run tick, write state back
  - Suitable for < 500 concurrent live operators
  - Known limitation: if a worker crashes after submitting an order but before writing the trade log, the trade may be orphaned

- **Phase 2+ (Temporal.io):**
  - Each operator is a persistent Temporal Workflow (not a one-shot task)
  - Operator tick = Temporal Activity (retryable, idempotent, with dedup key)
  - Order submission includes a `client_order_id` (dedup key) — if Temporal replays after a crash, the exchange rejects the duplicate rather than double-filling
  - State checkpointing handled by Temporal's event history (replaces Redis checkpointer)
  - Survives arbitrary worker crashes with exactly-once execution semantics
  - Scales to millions of concurrent workflows
  - **Migration:** `OperatorBase.tick()` maps directly onto a Temporal Activity. The LangGraph operator code does not change. Only the scheduling layer changes.

#### Exchange Gateway — Operator Layer
- Sits between Temporal workers and the exchange SDKs
- Per-exchange, per-API-key rate limiter (token bucket, configurable per exchange limits)
- All orders include a `client_order_id` for deduplication
- Fills are written to the immutable `trade_log` table by the gateway (not by operator code)
- Fill reconciler: periodic job that cross-checks `trade_log` against exchange fill history — catches missed webhook events
- API keys decrypted and injected here only — never visible in operator code or Temporal workflow history

#### Motis MCP Server
- Exposes remote execution tools to the Agent Service:
  - `market_data_*` — thin wrappers; heavy data logic lives as native skills in the Agent Service
  - `execute_paper_trade`, `execute_live_trade`, `get_positions` — trading execution (platform risk guard enforced here)
- Operator CRUD/invocation is a Motis operator-layer concern, not an MCP concern
- Research, backtest, data routing, and swarms are **NOT** MCP tools — native skills called in-process by the agent loop
- Platform risk guard is the last line of defense before any order reaches the Exchange Gateway

#### Arena Service
- Reads verified trade history from `trade_log` (written by Exchange Gateway, cross-verified by reconciler)
- Computes leaderboard metrics nightly from the verified trade_log window (preventing intraday gaming)
- WebSocket endpoint serves live leaderboard updates to the frontend
- Competition registration: snapshots operator AUM and equity at registration time via exchange API call
- Anti-gaming: operators that disconnect from the exchange mid-competition are automatically flagged and their leaderboard entry suspended

### 6.4 Model Layer (BYOM)

```
Master Agent model:    User-configurable (default: platform default)
Operator node model:   Per-operator configurable (default: inherits master)
Research swarms:       Inherit from master agent model config
```

All model calls go through an OpenAI-compatible interface. Users supply their own API key + base URL. Platform supplies a default endpoint.

Future: tiered model access — partnerships with providers for discounted fine-tuned trading models available to Motis subscribers.

### 6.5 Scaling Thresholds

| Operator Count | Architecture | What changes |
|---|---|---|
| **0 – 500** | Celery + Beat + per-operator polling | Nothing — this is Phase 0–1 |
| **500 – 5k** | Celery + Redis Streams (replace RDB broker) + shared market data cache | Replace Celery broker backend |
| **5k – 50k** | **Migrate to Temporal + Kafka fan-out** | Operator Runtime redeployed; operator code unchanged |
| **50k+** | Temporal + Kafka + dedicated Exchange Gateway pods per exchange | Exchange Gateway horizontally scaled; compliance surfaces |

**Key insight for agents implementing the operator runtime:** the `OperatorBase.tick()` interface is intentionally designed to be backend-agnostic. The caller (Celery task in Phase 0, Temporal Activity in Phase 2+) simply calls `await operator.tick()`. The LangGraph graph code inside never changes.

---

## 7. Infrastructure Requirements

### Conversation Layer (Phase 0+)

| Component | Technology | Notes |
|---|---|---|
| Frontend | Next.js + TypeScript | SSR for Marketplace SEO; CDN-hosted static assets |
| API Gateway | FastAPI (N pods) | Horizontal scaling behind load balancer |
| Agent Service | Python / Hermes fork (N pods) | Stateless per-request; SSE via Redis pub/sub relay |
| Finance Skills | Absorbed from Vibe-Trading (MIT) | In-process, `services/agent/motis_agent/skills/finance/` |
| Swarm Engine | Native LangGraph multi-agent | Presets in `services/agent/motis_agent/swarms/presets/` |
| Backtest Engine | Absorbed from Vibe-Trading (MIT) | In-process library |
| Auth | Supabase Auth + JWT | Row-level security per user |
| Session Cache | Redis | Conversation sessions, skill cache |
| Database | PostgreSQL (Supabase) | Users, operators, trade logs, memories |
| Blob Storage | S3 / Cloudflare R2 | Operator graph specs, backtest reports |
| Real-time (frontend) | SSE (agent stream) + WebSocket (arena leaderboard) | |
| Billing | Stripe | Subscriptions + marketplace payouts |
| Messaging Gateway | Hermes Gateway | Telegram, Discord — Phase 2 |

### Operator Layer — Phase 0–1 (Celery)

| Component | Technology | Notes |
|---|---|---|
| Operator Runtime | LangGraph + Celery workers | `OperatorBase.tick()` called by Celery task |
| Scheduler | Celery Beat | Per-operator interval scheduling |
| State Store | Redis (LangGraph checkpointer) | Operator state between ticks |
| Message Broker | Redis Streams | Celery broker backend |
| Market Data | Per-operator polling (native skills) | Suitable for < 500 operators |
| Exchange Connectivity | Hyperliquid SDK + Binance SDK + CCXT | Exchange Gateway in `services/mcp` |

### Operator Layer — Phase 2+ (Production Scale)

| Component | Technology | Notes |
|---|---|---|
| Operator Runtime | Temporal.io workers | Same `OperatorBase.tick()` interface; operator code unchanged |
| Workflow Engine | Temporal Server (self-hosted or Temporal Cloud) | Durable execution, dedup, replay |
| Market Data Bus | Kafka / Redpanda | One WS per (symbol, timeframe, exchange) → fan-out to all operators |
| Operator Dispatcher | Kafka consumer group | Subscribes to candle topics; emits operator_tick events |
| State Store | Temporal event history + Redis hot cache | Redis for O(1) state reads; Temporal for durability |
| Exchange Gateway | Dedicated pods per exchange | Rate limiter + order dedup + fill reconciler |
| Deployment | Kubernetes (Helm charts) | HPA on worker pods based on Temporal task queue depth |

### Shared Infrastructure

| Component | Technology | Notes |
|---|---|---|
| Secrets | AES-256 encrypted in PostgreSQL | User API keys never leave the Exchange Gateway |
| Deployment (dev) | Docker Compose | One command: `./scripts/dev.sh` |
| Deployment (prod) | Kubernetes | Helm charts in `infra/k8s/` |

---

## 8. Data Model (Conceptual)

```sql
-- Core
users (id, email, created_at, plan, byom_config_encrypted, platform_risk_limits)
exchange_connections (id, user_id, exchange, api_key_encrypted, api_secret_encrypted, label)

-- Agent
conversations (id, user_id, created_at, title)
messages (id, conversation_id, role, content, tool_calls, created_at)
memories (id, user_id, type, content, created_at)
skills (id, user_id, name, code, description, created_at, version)

-- Operators
operators (id, user_id, name, state, version, graph_spec_url, risk_config, 
           asset_universe, trigger_config, model_config, created_at, updated_at)
operator_versions (id, operator_id, version, graph_spec_url, created_at)
operator_state (operator_id, state_json, checkpoint_at)   -- Redis-primary, DB-backup
backtest_results (id, operator_id, run_at, config, metrics_json, report_url)

-- Trading
trade_log (id, operator_id, user_id, exchange, symbol, side, size, 
           entry_price, fill_price, fill_at, fee, pnl, verified_at, 
           exchange_order_id)  -- immutable append-only
positions (operator_id, symbol, exchange, size, avg_entry, current_pnl, updated_at)

-- Arena
competitions (id, name, aum_class, start_at, end_at, asset_filter, scoring_metric)
competition_entries (id, competition_id, user_id, operator_id, 
                     starting_equity, registered_at)
competition_snapshots (entry_id, snapshot_date, equity, pnl, sharpe, drawdown)
  -- populated nightly from verified trade_log

-- Marketplace
marketplace_listings (id, operator_id, publisher_user_id, name, description,
                      strategy_style, asset_class, price_usd_month, 
                      verified_stats_json, listed_at, status)
subscriptions (id, subscriber_user_id, listing_id, subscriber_operator_id,
               started_at, cancelled_at, stripe_subscription_id)
arena_badges (listing_id, competition_id, rank, aum_class, period)
```

---

## 9. Open Questions & Risks

| # | Question | Current Answer | Risk |
|---|---|---|---|
| 1 | Operator node code sandboxing | Operator code runs in Celery/Temporal workers. Restrict imports with `importlib` hooks + resource limits (ulimit, cgroups) | Security risk if not hardened before marketplace |
| 2 | Exchange API key security | AES-256 encrypted in DB, decrypted and injected only in Exchange Gateway. Keys never appear in Temporal workflow history or operator code | Highest security priority — must be audited before Phase 2 |
| 3 | Arena AUM verification | Platform snapshots equity via exchange API at registration. AUM class locked at registration time — moving funds mid-competition triggers disqualification flag | Define precise rules in arena service before Phase 3 |
| 4 | Operator model costs at scale | User-supplied API keys = cost on user. Platform default endpoint has token-based billing | Document clearly in onboarding; add cost estimator UI |
| 5 | Marketplace operator updates | Subscribers pinned to a version, notified of updates, can opt in per-version | Version pinning must be implemented before marketplace launch |
| 6 | Regulatory (live trading, marketplace) | Jurisdiction-dependent. Marketplace = copy trading infrastructure (not investment advice). Need legal review. | High — engage counsel before Phase 2 launch |
| 7 | Vibe-Trading license | MIT — freely usable, attribution preserved in file headers | Low risk |
| 8 | Hermes fork maintenance | Hermes is active. Minimize divergence — consider contributing multi-user work upstream as an optional mode | Medium — track upstream releases |
| 9 | Celery → Temporal migration | `OperatorBase.tick()` is designed backend-agnostic. Migration = replace Celery task dispatch with Temporal Activity. Operator LangGraph code unchanged. | Low code risk; Temporal infra setup is non-trivial — plan 2–3 weeks |
| 10 | Exchange rate limits at scale | Exchange Gateway implements per-key token bucket rate limiter. At >500 operators per exchange key, sub-accounts or multiple keys required | Medium — design sub-account routing before Phase 2 |
| 11 | Kafka/Redpanda introduction | Not needed until Phase 2 (>500 operators). Adds operational complexity. Consider Redpanda (Kafka-compatible, single binary) to reduce ops burden | Low in Phase 0–1; plan infrastructure before Phase 2 |

---

## 10. Phased Build Roadmap

### Phase 0 — Foundation (Weeks 1–4)
- [x] Monorepo scaffold: `packages/`, `services/agent/`, `services/mcp/`, `services/platform/`, `web/`
- [x] Shared packages: `motis-shared` (Pydantic models, types) + `motis-operator-sdk` (LangGraph base)
- [x] Finance skills skeleton: 68 skill stubs across 7 categories (absorbed from Vibe-Trading)
- [x] SMC analysis skill: BOS, CHoCH, liquidity sweeps, order blocks, FVG (fully implemented)
- [x] Data routing skill: 5-source auto-fallback (ccxt, yfinance, akshare, okx, tushare)
- [x] SwarmRunner: 29 preset configs, `crypto_trading_desk` preset written
- [x] MCP server skeleton: execution tools + risk guard stub
- [x] Platform API gateway skeleton: FastAPI + routes
- [x] Operator runtime: Celery worker skeleton
- [x] `docker-compose.yml`: full local stack (postgres, redis, all services)
- [ ] **Fork Hermes Agent** → clone repo into `services/agent/`, gut single-user FS assumptions, adapt core loop to multi-user web
- [ ] Agent core loop: `core/loop.py` — Hermes ReAct loop adapted for SSE streaming + UserContext
- [ ] Agent memory: `core/memory.py` — DB-backed MemoryStore (replaces Hermes filesystem MEMORY.md)
- [ ] Agent skill runner: `core/skills.py` — SkillRegistry auto-discovers finance skills
- [ ] Implement individual finance skill stubs: `ccxt_ohlcv.py`, `yfinance_data.py`, `technical.py`
- [ ] Supabase setup: auth, user table, DB schema (run Alembic migrations)
- [ ] Platform auth middleware: JWT validation → UserContext headers → agent service
- [ ] Basic chat UI (Next.js): SSE message stream rendering, conversation history

**Milestone:** User can log in, chat with the Master Agent, and receive a streamed research swarm result.

---

### Phase 1 — Operators (Weeks 5–10)
- [ ] `OperatorBase` fully wired: Redis checkpointing, tick scheduling, state serialization
- [ ] Celery Beat: dynamic schedule registration per operator trigger_config
- [ ] `BacktestOperator`: native backtest engine integration, metrics, `ai_critique` node
- [ ] `PaperTradeOperator`: simulated fills, real data via native data routing skill
- [ ] `ResearchOperator`: wraps native SwarmRunner, streams per-agent events
- [ ] Operator Builder: Master Agent conversation-to-operator flow (NL → LangGraph spec)
- [ ] Operators sidebar in frontend (state badge, P&L, quick actions)
- [ ] Operator detail view: graph visualization, trade log, run log stream
- [ ] Exchange connections: Hyperliquid + Binance (migrated from existing project into `services/mcp/motis_mcp/execution/exchanges/`)
- [ ] Operator run log streaming to frontend (explicit agent loop messages)

**Milestone:** User can describe a strategy, have the agent build and backtest an Operator, and run it in paper trade mode.

---

### Phase 2 — Live Trade + Marketplace (Weeks 11–18)

**Operator Infrastructure (before any live money):**
- [ ] `LiveTradeOperator` with two-layer risk enforcement (operator rules + platform guard)
- [ ] Exchange Gateway: per-key rate limiter + order dedup (`client_order_id`) + fill reconciler
- [ ] Immutable `trade_log` table: written by Exchange Gateway only, append-only, exchange-verified fills
- [ ] CCXT integration for broader exchange support (beyond Hyperliquid + Binance)
- [ ] Operator versioning + rollback UI
- [ ] BYOM: user-configurable model endpoint for master agent + operators
- [ ] **Scaling gate:** benchmark operator runtime at 500 concurrent live operators. If Celery shows timing degradation, begin Temporal migration now (before Phase 3 operator count explosion from marketplace)

**Marketplace:**
- [ ] Performance verification pipeline: compute Sharpe, max DD, win rate from `trade_log`; attach "Verified by Motis" badge
- [ ] Operator listing flow: 30-day live history gate, publisher KYC, description drafting (agent-assisted)
- [ ] Marketplace discovery UI: filters, algorithm-ranked feed, listing detail with verified trade log viewer
- [ ] Subscription flow: operator spec clone → parameterize with subscriber's exchange keys → instantiate
- [ ] Stripe billing integration: subscription payments + marketplace publisher payouts (80/20 split)
- [ ] Legal review completed before launch (copy trading jurisdiction analysis)

**Milestone:** Users can run live operators, publish verified operators to the Marketplace, and subscribers can have operators instantiated in their own exchange accounts.

---

### Phase 3 — Arena (Weeks 19–24)
- [ ] Competition schema + registration flow
- [ ] Exchange sync job: pull fills, populate verified trade log, compute equity
- [ ] Nightly leaderboard computation
- [ ] Competition UI: lobby, leaderboard (WebSocket), entry flow
- [ ] Arena badges + post-competition report generation
- [ ] Featured section on Marketplace for Arena winners
- [ ] Anti-gaming rules + monitoring

**Milestone:** First live Arena competition runs end-to-end.

---

### Phase 4 — Scale Infrastructure (Weeks 25–32)

**Operator Layer Scaling (trigger: >500 live operators):**
- [ ] Redpanda (Kafka-compatible) deployment: market data bus replacing per-operator polling
- [ ] Operator Dispatcher service: subscribes to candle/orderbook topics, emits targeted `operator_tick` events
- [ ] **Temporal.io migration:** replace Celery workers with Temporal workers. `OperatorBase.tick()` interface unchanged — only scheduling layer changes. Estimated: 2–3 weeks.
- [ ] Exchange Gateway pods: one per exchange, horizontally scaled, with per-key rate limiter and sub-account routing
- [ ] Kubernetes (Helm): HPA on Temporal worker pods based on task queue depth

**Conversation Layer Scaling:**
- [ ] Agent Service: N pods behind load balancer; SSE via Redis pub/sub relay (for pod-agnostic streaming)
- [ ] Redis Cluster for session cache and operator state hot cache

**Product:**
- [ ] Hermes Gateway: Telegram/Discord notifications for live operator events (fill, SL hit, daily report)
- [ ] Operator performance analytics dashboard (drawdown curves, rolling Sharpe, attribution)
- [ ] Model provider partnerships (discounted/fine-tuned trading models for Motis subscribers)
- [ ] Mobile app (React Native, via Hermes Gateway backend)
- [ ] Advanced research: custom swarm presets, uploaded document analysis (earnings PDFs, whitepapers)
- [ ] Pine Script v6 export in UI
- [ ] Public API for power users / institutional accounts

**Milestone:** Platform supports 5k+ concurrent live operators with sub-second tick precision and exactly-once execution semantics.

---

## Appendix A: Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-10 | Fork Hermes Agent as master agent base | Already handles ReAct loop, memory, skills, MCP, context compression. Adapt for multi-user rather than rewrite. |
| 2026-04-10 | Absorb Vibe-Trading in-process (not MCP sidecar) | Eliminates a service, removes network overhead, enables free skill composition inside operator nodes. MIT licensed. |
| 2026-04-10 | Celery in Phase 0, Temporal in Phase 2+ | Celery is zero additional complexity for <500 operators. Temporal adds durability + dedup guarantees needed before marketplace operator count explodes. |
| 2026-04-10 | Kafka/Redpanda in Phase 4 | Not needed until scale forces it. Redpanda preferred (Kafka-compatible, single binary, lower ops overhead). |
| 2026-04-10 | Arena = AUM-class live trading (not shared sandbox) | Each operator trades independently in its own exchange account. Platform verifies via exchange API — not self-reported. |
| 2026-04-10 | Platform-verified marketplace performance only | 30-day live history minimum, stats computed from immutable trade_log cross-checked against exchange fills. No self-reported numbers. |
| 2026-04-10 | Claude Managed Agents = optional backend, not core | Vendor lock-in + cost at scale + limited operator graph control outweigh the convenience. Operator spec format stays portable. |

---

*End of PRD v0.3*
