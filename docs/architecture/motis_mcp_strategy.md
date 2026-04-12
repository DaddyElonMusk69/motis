# MOTIS MCP Server Strategy

**Version:** 0.1  
**Date:** April 10, 2026  
**Status:** Planning Phase

---

## Executive Summary

This document outlines the MCP (Model Context Protocol) server architecture for MOTIS. Based on analysis of existing solutions and MOTIS requirements, we recommend a **hybrid approach**: integrate existing open-source CCXT MCP servers for market data, and build custom MOTIS MCP servers for execution, operator management, and platform-specific features.

**Key Decisions:**
1. **Market Data**: Use existing `doggybee/mcp-server-ccxt` (TypeScript, high-performance) or `lazy-dinosaur/ccxt-mcp` (Python, feature-rich)
2. **Execution**: Build custom MOTIS MCP server with platform risk guard and multi-user support
3. **Operator Management**: Build custom MCP server for operator CRUD and invocation
4. **Research Tools**: Keep as native skills (not MCP) per PRD guidance

---

## 1. MCP Ecosystem Analysis

### 1.1 What is MCP?

Model Context Protocol (MCP) is an open standard by Anthropic that enables LLMs to interact with external tools and data sources through a standardized interface. As of 2026, the MCP ecosystem includes 1,000+ servers covering databases, APIs, file systems, cloud services, and more.

**Key Benefits for MOTIS:**
- **Industry Standard**: Anthropic-backed, broad ecosystem support
- **Better Isolation**: Tools run in separate processes, reducing security risks
- **Extensibility**: Users can add custom MCP servers without modifying MOTIS core
- **Multi-User Support**: MCP servers can handle authentication and user context

---

## 2. Existing CCXT MCP Servers

### 2.1 doggybee/mcp-server-ccxt (TypeScript)

**Repository**: [https://github.com/doggybee/mcp-server-ccxt](https://github.com/doggybee/mcp-server-ccxt)  
**Language**: TypeScript/Node.js  
**License**: MIT  
**NPM Package**: `@mcpfun/mcp-server-ccxt`

**Features:**
- 20+ cryptocurrency exchanges (Binance, Coinbase, Kraken, Bybit, OKX, etc.)
- Spot, futures, swap markets
- LRU caching with adaptive TTLs (ticker: 10s, orderbook: 5s, markets: 1h)
- Adaptive rate limiting with exponential backoff
- Proxy support
- 30+ tools (public + private APIs)

**Public API Tools:**
- `list-exchanges`, `get-ticker`, `batch-get-tickers`
- `get-orderbook`, `get-ohlcv`, `get-trades`
- `get-markets`, `get-exchange-info`
- `get-leverage-tiers`, `get-funding-rates`
- `get-positions`, `get-open-orders`, `get-order-history`

**Private API Tools (requires API keys):**
- `account-balance`, `place-market-order`, `place-limit-order`
- `cancel-order`, `cancel-all-orders`
- `set-leverage`, `set-margin-mode`
- `place-futures-market-order`, `place-futures-limit-order`
- `transfer-funds`

**Configuration & Utility Tools:**
- `cache-stats`, `clear-cache`, `set-log-level`
- `get-proxy-config`, `set-proxy-config`
- `set-market-type`, `set-default-exchange`, `system-info`

**Pros:**
- High-performance (optimized caching, rate limiting)
- Well-maintained (active development in 2026)
- TypeScript (type-safe, good for production)
- Comprehensive tool set

**Cons:**
- TypeScript (MOTIS is Python-based)
- Single-user design (API keys in environment variables)
- No multi-user authentication/authorization
- Execution tools bypass MOTIS risk guard

---

### 2.2 lazy-dinosaur/ccxt-mcp (Python)

**Repository**: [https://github.com/lazy-dinosaur/ccxt-mcp](https://github.com/lazy-dinosaur/ccxt-mcp)  
**Language**: Python  
**License**: MIT  
**NPM Package**: `@lazydino/ccxt-mcp`

**Features:**
- 100+ cryptocurrency exchanges via CCXT
- Multi-account support (named accounts with separate API keys)
- Spot and futures markets
- Advanced trading analytics (win rate, profit factor, R-multiple, consecutive wins/losses)
- Position management (capital ratio trading, leverage setting, dynamic position sizing)
- Risk management (technical indicator-based stop loss, volatility-based SL/TP, max loss limits)

**Account Configuration:**
```json
{
  "accounts": [
    {
      "name": "bybit_main",
      "exchangeId": "bybit",
      "apiKey": "YOUR_API_KEY",
      "secret": "YOUR_SECRET_KEY",
      "defaultType": "spot"
    },
    {
      "name": "bybit_futures",
      "exchangeId": "bybit",
      "apiKey": "YOUR_API_KEY",
      "secret": "YOUR_SECRET_KEY",
      "defaultType": "swap"
    }
  ]
}
```

**Pros:**
- Python (same language as MOTIS)
- Multi-account support (closer to multi-user needs)
- Advanced trading analytics (useful for Arena/Marketplace)
- Risk management features (can inform MOTIS risk guard)

**Cons:**
- Still single-user (accounts in config file, not per-user database)
- No platform-level risk guard enforcement
- Execution tools bypass MOTIS trade log
- Less performance optimization than doggybee

---

## 3. MOTIS MCP Architecture

### 3.1 Design Principles

Per MOTIS PRD Section 6.2-6.3:

1. **Platform Risk Guard is Non-Negotiable**: ALL trading execution must go through MOTIS MCP server with platform-level risk checks
2. **Multi-User by Design**: Each user has separate API keys, risk limits, and trade logs
3. **Immutable Trade Log**: All fills written by MOTIS MCP server (source of truth for Arena + Marketplace)
4. **API Key Security**: Keys encrypted in DB, decrypted and injected at MCP layer, never exposed to operator code
5. **Skills are Native, Not MCP**: Research, backtest, data routing, and swarms run in-process (not as MCP tools)

---

### 3.2 Recommended MCP Server Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MOTIS PLATFORM                               │
│                                                                      │
│  ══════════════════ CONVERSATION LAYER (stateless) ════════════════  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │    Agent Service (Hermes fork, N pods)                        │   │
│  │  68 finance skills + 29 swarms in-process (NOT MCP)           │   │
│  └──────────────────────┬───────────────────────────────────────┘   │
│                         │ MCP calls                                  │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              MCP Server Layer (3 servers)                     │   │
│  │                                                                │   │
│  │  ┌────────────────────────────────────────────────────────┐   │   │
│  │  │  1. MOTIS Execution MCP (Python)                        │   │   │
│  │  │     - execute_paper_trade, execute_live_trade           │   │   │
│  │  │     - get_positions, get_account_balance                │   │   │
│  │  │     - Platform risk guard enforcement                   │   │   │
│  │  │     - Multi-user auth (JWT → user_id)                   │   │   │
│  │  │     - API key decryption & injection                    │   │   │
│  │  │     - Immutable trade_log writes                        │   │   │
│  │  └────────────────────────────────────────────────────────┘   │   │
│  │                                                                │   │
│  │  ┌────────────────────────────────────────────────────────┐   │   │
│  │  │  2. CCXT Market Data MCP (TypeScript or Python)         │   │   │
│  │  │     - Use doggybee/mcp-server-ccxt OR                   │   │   │
│  │  │     - Use lazy-dinosaur/ccxt-mcp                        │   │   │
│  │  │     - Public API only (no execution)                    │   │   │
│  │  │     - get_ticker, get_orderbook, get_ohlcv, etc.        │   │   │
│  │  └────────────────────────────────────────────────────────┘   │   │
│  │                                                                │   │
│  │  ┌────────────────────────────────────────────────────────┐   │   │
│  │  │  3. MOTIS Operator MCP (Python)                         │   │   │
│  │  │     - operator_create, operator_update, operator_delete │   │   │
│  │  │     - operator_invoke, operator_status                  │   │   │
│  │  │     - operator_pause, operator_resume                   │   │   │
│  │  │     - Multi-user scoped (user can only see own ops)     │   │   │
│  │  └────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ═══════════════════ OPERATOR LAYER (event-driven) ════════════════  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Operator Runtime (Celery / Temporal)             │   │
│  │  Operators call MOTIS Execution MCP for trades                │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 3.3 MCP Server Breakdown

#### 3.3.1 MOTIS Execution MCP (Custom, Python)

**Purpose**: Platform chokepoint for ALL trading execution

**Location**: `services/mcp/motis_execution_mcp/`

**Tools**:
- `execute_paper_trade` — Simulated fills, written to trade_log with `is_paper=True`
- `execute_live_trade` — Live exchange execution, platform risk guard enforced
- `get_positions` — Current open positions for an operator
- `get_account_balance` — Account balance/equity for an operator's exchange account

**Key Features**:
1. **Multi-User Authentication**: Each MCP call includes `operator_id` → resolves to `user_id` → loads user's API keys
2. **Platform Risk Guard**: Enforced BEFORE any exchange call (cannot be bypassed by operator code)
3. **API Key Security**: Keys encrypted in PostgreSQL, decrypted at MCP layer, never exposed to operator code
4. **Immutable Trade Log**: All fills written to `trade_log` table (source of truth for Arena + Marketplace)
5. **Paper/Live Routing**: Same operator code, different MCP tool (`execute_paper_trade` vs `execute_live_trade`)

**Implementation Status**: Partially implemented (see `services/mcp/motis_execution_mcp/tools.py`)

**Next Steps**:
- Implement live trade execution (decrypt keys, route to exchange)
- Implement position and balance fetching
- Add fill reconciler (cross-check trade_log against exchange fill history)

---

#### 3.3.2 CCXT Market Data MCP (Existing, TypeScript or Python)

**Purpose**: Public market data access (no execution)

**Options**:

**Option A: doggybee/mcp-server-ccxt (TypeScript)**
- **Pros**: High-performance, well-maintained, comprehensive caching/rate limiting
- **Cons**: TypeScript (requires Node.js runtime alongside Python)
- **Integration**: Run as separate process, MOTIS Agent Service calls via MCP protocol

**Option B: lazy-dinosaur/ccxt-mcp (Python)**
- **Pros**: Python (same language as MOTIS), multi-account support
- **Cons**: Less performance optimization, still single-user design
- **Integration**: Fork and adapt for multi-user (remove execution tools, keep market data only)

**Option C: Build Custom (Python)**
- **Pros**: Full control, optimized for MOTIS needs
- **Cons**: Reinventing the wheel, maintenance burden
- **Integration**: Build from scratch using CCXT library

**Recommendation**: **Option A (doggybee/mcp-server-ccxt)** for Phase 0-1
- Reason: High-performance, production-ready, comprehensive tool set
- Trade-off: Requires Node.js runtime, but MCP protocol abstracts this away
- Future: Consider Option B or C if TypeScript dependency becomes a bottleneck

**Tools to Expose** (public API only):
- `list-exchanges`, `get-ticker`, `batch-get-tickers`
- `get-orderbook`, `get-ohlcv`, `get-trades`
- `get-markets`, `get-exchange-info`
- `get-leverage-tiers`, `get-funding-rates`

**Tools to DISABLE** (execution must go through MOTIS Execution MCP):
- `account-balance`, `place-market-order`, `place-limit-order`
- `cancel-order`, `cancel-all-orders`
- `set-leverage`, `set-margin-mode`
- `place-futures-market-order`, `place-futures-limit-order`
- `transfer-funds`

---

#### 3.3.3 MOTIS Operator MCP (Custom, Python)

**Purpose**: Operator CRUD and invocation from Master Agent

**Location**: `services/mcp/motis_operator_mcp/` (scaffolded, not implemented)

**Tools**:
- `operator_create` — Create a new operator spec (draft state)
- `operator_update` — Update operator code, parameters, or risk limits
- `operator_delete` — Delete an operator (archive)
- `operator_invoke` — Trigger an operator run (backtest, research, or ad-hoc paper trade)
- `operator_status` — Get operator state, last run time, P&L, etc.
- `operator_pause` — Pause a live/paper operator
- `operator_resume` — Resume a paused operator
- `operator_list` — List all operators for the current user

**Key Features**:
1. **Multi-User Scoped**: Each user can only see/manage their own operators
2. **State Machine Enforcement**: Operators transition through states (draft → validating → paper → live → paused → archived)
3. **Quality Gate Integration**: `operator_invoke` triggers Quality Gate checks before paper/live deployment
4. **Operator Runtime Integration**: Calls Celery/Temporal to schedule operator ticks

**Implementation Status**: Not implemented (tools.py file missing)

**Next Steps**:
- Implement operator CRUD tools
- Integrate with operator runtime (Celery Beat for Phase 0-1)
- Add Quality Gate checks (5 blockers for paper, 10 for live)

---

## 4. Skills vs. MCP Tools: What Goes Where?

Per MOTIS PRD Section 5.1, **skills are native (in-process), not MCP tools**. This is a critical architectural decision.

### 4.1 Native Skills (NOT MCP)

**Location**: `services/agent/motis_agent/skills/finance/`

**What Belongs Here**:
- **Data Routing** (`data/routing.py`) — Auto-fallback across 5 data sources
- **Technical Analysis** (`analysis/smc.py`, `analysis/candlestick.py`, etc.) — Signal generation
- **Quantitative Analysis** (`analysis/factor.py`, `analysis/multi_factor.py`) — Alpha factor research
- **Fundamental Analysis** (`analysis/financial_statement.py`, `analysis/valuation.py`) — Equity research
- **Macro Research** (`research/global_macro.py`, `research/onchain_analysis.py`) — Research context
- **Crypto Research** (`research/perp_funding_basis.py`, `research/liquidation_heatmap.py`) — Crypto-specific research
- **Reporting** (`reporting/strategy_generate.py`, `reporting/backtest_diagnose.py`) — Documentation generation

**Why Native?**
- **Performance**: No IPC overhead, direct Python function calls
- **Context Sharing**: Skills can access agent's conversation context, memory, and user config
- **Simplicity**: No need for MCP protocol overhead for in-process logic
- **Skill Registry**: Agent auto-discovers skills from `skills/` directory

**Already Ported**: 83 skills (see `docs/vibe_trading_porting_complete.md`)

---

### 4.2 MCP Tools (External Process)

**What Belongs Here**:
- **Trading Execution** — Platform risk guard, API key security, immutable trade log
- **Market Data** — High-performance caching, rate limiting, multi-exchange support
- **Operator Management** — Operator CRUD, state machine, runtime integration
- **External Integrations** — Future: news APIs, SEC filings, on-chain data providers

**Why MCP?**
- **Security Isolation**: Execution tools run in separate process, reducing attack surface
- **Multi-User Support**: MCP servers can handle authentication and user context
- **Extensibility**: Users can add custom MCP servers without modifying MOTIS core
- **Rate Limiting**: MCP servers can enforce per-user rate limits

---

## 5. Swarms and Backtest Engine: Native, Not MCP

### 5.1 Swarms (ResearchOperator)

**Location**: `services/agent/motis_agent/swarms/`

**Structure**:
- **Presets**: `swarms/presets/*.yaml` (29 presets from Vibe Trading)
- **Runner**: `swarms/runner.py` (SwarmRunner class)
- **Integration**: Wrapped in `ResearchOperator` (LangGraph)

**Why Native?**
- Per PRD Section 5.2-5.4, swarms are **always run as ResearchOperators**, not inline in agent loop
- ResearchOperator is a LangGraph StateGraph with persistence, scheduling, and sidebar visibility
- Swarm results are persisted to DB + S3, visible as completed operator runs
- No need for MCP protocol overhead — swarms are internal MOTIS logic

**Implementation Status**: Not yet ported (29 presets need to be ported from Vibe Trading)

---

### 5.2 Backtest Engine (BacktestOperator)

**Location**: `services/agent/motis_agent/backtest/`

**Structure**:
- **Engines**: `backtest/engines/` (crypto.py, global_equity.py, china_a.py, options_portfolio.py)
- **Loaders**: `backtest/loaders/` (ccxt_loader.py, yfinance_loader.py, akshare_loader.py, etc.)
- **Metrics**: `backtest/metrics.py` (Sharpe, Sortino, Calmar, max drawdown, win rate, etc.)
- **Runner**: `backtest/runner.py` (orchestrates strategy parsing, data loading, engine selection, metrics calculation)

**Why Native?**
- Per PRD Section 5.4, backtests are **always run as BacktestOperators**, not inline in agent loop
- BacktestOperator is a LangGraph StateGraph with nodes: `strategy_parse → data_fetch → engine_run → metrics → ai_critique → persist_report`
- Backtest results are attached to Operator spec, displayed in sidebar, referenced in Marketplace listings
- No need for MCP protocol overhead — backtest engine is internal MOTIS logic

**Implementation Status**: Not yet ported (backtest engine needs to be ported from Vibe Trading)

---

## 6. Implementation Roadmap

### Phase 0: Foundation (Immediate)

**Goal**: Get MOTIS Execution MCP and CCXT Market Data MCP working

**Tasks**:
1. **MOTIS Execution MCP**:
   - Implement `execute_live_trade` (decrypt keys, route to exchange via CCXT)
   - Implement `get_positions` (fetch from PostgreSQL positions table)
   - Implement `get_account_balance` (fetch from exchange via decrypted keys)
   - Add platform risk guard checks (max leverage, max position size, daily loss limit)
   - Write fills to `trade_log` table (immutable, source of truth)

2. **CCXT Market Data MCP**:
   - Deploy `doggybee/mcp-server-ccxt` as separate Node.js process
   - Configure MOTIS Agent Service to call CCXT MCP via MCP protocol
   - Disable execution tools (only expose public API tools)
   - Test market data fetching (ticker, orderbook, OHLCV)

3. **Integration Testing**:
   - Master Agent calls CCXT MCP for market data
   - Master Agent calls MOTIS Execution MCP for paper trades
   - Verify trade_log entries are written correctly
   - Verify platform risk guard rejects invalid trades

**Success Criteria**:
- Master Agent can fetch BTC/USDT ticker from Binance via CCXT MCP
- Master Agent can execute a paper trade via MOTIS Execution MCP
- Paper trade is written to trade_log with `is_paper=True`
- Platform risk guard rejects trades exceeding max position size

---

### Phase 1: Operators (Next)

**Goal**: Enable operators to call MOTIS Execution MCP for live trades

**Tasks**:
1. **MOTIS Operator MCP**:
   - Implement `operator_create`, `operator_update`, `operator_delete`
   - Implement `operator_invoke` (trigger backtest, research, or paper trade)
   - Implement `operator_status`, `operator_pause`, `operator_resume`
   - Integrate with Celery Beat (schedule operator ticks)

2. **Operator Runtime**:
   - Implement `LiveTradeOperator` and `PaperTradeOperator` LangGraph nodes
   - Operators call MOTIS Execution MCP for trades (not CCXT MCP)
   - Operators call CCXT MCP for market data (read-only)

3. **Quality Gate**:
   - Implement 5 blocker checks for paper trading (code validation, risk limits, data availability, etc.)
   - Implement 10 blocker checks for live trading (+ exchange connection, API key validation, etc.)

**Success Criteria**:
- Master Agent can create a `PaperTradeOperator` via MOTIS Operator MCP
- Operator runs on schedule (Celery Beat), fetches market data (CCXT MCP), executes paper trades (MOTIS Execution MCP)
- Operator state visible in sidebar (P&L, last run time, trade log)
- Quality Gate blocks paper → live transition if checks fail

---

### Phase 2: Marketplace (Later)

**Goal**: Enable Arena and Marketplace features

**Tasks**:
1. **Arena Service**:
   - Read verified trade history from `trade_log` (written by MOTIS Execution MCP)
   - Compute leaderboard metrics (Sharpe, total return, max drawdown)
   - WebSocket endpoint for live leaderboard updates

2. **Marketplace Service**:
   - Operator publishing (verified performance chart, trade log viewer)
   - Operator subscription (clone spec, parameterize for subscriber)
   - Revenue sharing (platform fee, publisher royalty)

3. **Fill Reconciler**:
   - Periodic job that cross-checks `trade_log` against exchange fill history
   - Catches missed webhook events, flags discrepancies

**Success Criteria**:
- Arena leaderboard shows live operators ranked by Sharpe ratio
- Marketplace listings show verified performance charts
- Fill reconciler detects and flags missed fills

---

## 7. Security Considerations

### 7.1 API Key Security

**Threat Model**: Operator code is user-generated (or marketplace-subscribed). It could be malicious or compromised.

**Mitigation**:
1. **Encryption at Rest**: API keys encrypted in PostgreSQL using AES-256
2. **Decryption at MCP Layer**: Keys decrypted only at MOTIS Execution MCP layer, never exposed to operator code
3. **No Direct Exchange Access**: Operators cannot call exchange APIs directly — all calls go through MOTIS Execution MCP
4. **Audit Log**: All MCP calls logged with `user_id`, `operator_id`, `tool_name`, `arguments`, `timestamp`

---

### 7.2 Platform Risk Guard

**Threat Model**: Operator code could attempt to bypass risk limits (e.g., max leverage, max position size, daily loss limit).

**Mitigation**:
1. **Enforcement at MCP Layer**: Platform risk guard runs BEFORE any exchange call
2. **Cannot Be Bypassed**: Operator code cannot call exchange APIs directly — all calls go through MOTIS Execution MCP
3. **Per-User Limits**: Risk limits stored in `user_risk_limits` table, enforced per-user
4. **Kill Switch**: Global kill switch can halt all live trading instantly (e.g., during platform maintenance or market crash)

---

### 7.3 Multi-User Isolation

**Threat Model**: User A's operator could attempt to access User B's API keys or trade log.

**Mitigation**:
1. **User Context Injection**: Each MCP call includes `operator_id` → resolves to `user_id` → loads user's API keys and risk limits
2. **Database Row-Level Security**: PostgreSQL RLS policies ensure users can only access their own data
3. **Operator Scoping**: Operators can only call MOTIS Execution MCP with their own `operator_id`

---

## 8. Performance Considerations

### 8.1 Market Data Caching

**Challenge**: Operators may request the same market data (e.g., BTC/USDT ticker) multiple times per second.

**Solution**:
- Use `doggybee/mcp-server-ccxt` with built-in LRU caching (ticker: 10s TTL, orderbook: 5s TTL)
- Alternative: Build custom caching layer in MOTIS (Redis-backed)

---

### 8.2 Rate Limiting

**Challenge**: Operators may exceed exchange rate limits, causing API bans.

**Solution**:
- Use `doggybee/mcp-server-ccxt` with adaptive rate limiting (exponential backoff)
- Alternative: Build custom rate limiter in MOTIS (token bucket per exchange, per user)

---

### 8.3 MCP Protocol Overhead

**Challenge**: MCP protocol adds IPC overhead (JSON serialization, process communication).

**Solution**:
- Use MCP only for execution and market data (high-value, low-frequency calls)
- Keep skills native (in-process, no IPC overhead)
- Batch market data requests where possible (e.g., `batch-get-tickers`)

---

## 9. Open Questions

### 9.1 CCXT MCP: TypeScript vs. Python?

**Question**: Should we use `doggybee/mcp-server-ccxt` (TypeScript) or `lazy-dinosaur/ccxt-mcp` (Python)?

**Recommendation**: **doggybee/mcp-server-ccxt** (TypeScript) for Phase 0-1
- **Reason**: High-performance, production-ready, comprehensive caching/rate limiting
- **Trade-off**: Requires Node.js runtime, but MCP protocol abstracts this away
- **Future**: Re-evaluate in Phase 2 if TypeScript dependency becomes a bottleneck

---

### 9.2 Should We Fork or Use As-Is?

**Question**: Should we fork existing CCXT MCP servers or use them as-is?

**Recommendation**: **Use as-is** for Phase 0-1, **fork if needed** in Phase 2
- **Reason**: Both `doggybee` and `lazy-dinosaur` are MIT-licensed, actively maintained
- **Trade-off**: Less control, but lower maintenance burden
- **Future**: Fork if we need MOTIS-specific features (e.g., multi-user auth, custom caching)

---

### 9.3 Should We Build a Unified MOTIS MCP Server?

**Question**: Should we merge MOTIS Execution MCP, CCXT Market Data MCP, and MOTIS Operator MCP into a single server?

**Recommendation**: **Keep separate** for Phase 0-1, **consider merging** in Phase 2
- **Reason**: Separation of concerns (execution vs. market data vs. operator management)
- **Trade-off**: More processes to manage, but better isolation and scalability
- **Future**: Merge if process management becomes a bottleneck

---

## 10. Next Steps

### Immediate (This Week)

1. **Decision**: Choose CCXT MCP server (doggybee vs. lazy-dinosaur)
2. **Deploy**: Set up chosen CCXT MCP server as separate process
3. **Test**: Master Agent calls CCXT MCP for market data (ticker, orderbook, OHLCV)
4. **Implement**: Complete `execute_live_trade` in MOTIS Execution MCP

### Short-Term (Next 2 Weeks)

1. **Implement**: `get_positions` and `get_account_balance` in MOTIS Execution MCP
2. **Implement**: Platform risk guard checks (max leverage, max position size, daily loss limit)
3. **Test**: End-to-end paper trade flow (Master Agent → MOTIS Execution MCP → trade_log)
4. **Document**: MCP server deployment guide (Docker, Kubernetes)

### Medium-Term (Next Month)

1. **Implement**: MOTIS Operator MCP (operator CRUD, invocation, status)
2. **Implement**: Operator runtime integration (Celery Beat scheduling)
3. **Implement**: Quality Gate checks (5 blockers for paper, 10 for live)
4. **Test**: End-to-end operator flow (create → backtest → paper trade → live trade)

---

## 11. References

### External Resources

- **MCP Specification**: [https://modelcontextprotocol.io](https://modelcontextprotocol.io)
- **doggybee/mcp-server-ccxt**: [https://github.com/doggybee/mcp-server-ccxt](https://github.com/doggybee/mcp-server-ccxt)
- **lazy-dinosaur/ccxt-mcp**: [https://github.com/lazy-dinosaur/ccxt-mcp](https://github.com/lazy-dinosaur/ccxt-mcp)
- **CCXT Library**: [https://github.com/ccxt/ccxt](https://github.com/ccxt/ccxt)
- **Anthropic MCP Docs**: [https://docs.anthropic.com/mcp](https://docs.anthropic.com/mcp)

### Internal Documents

- **MOTIS PRD**: `docs/motis_prd.md` (Sections 5.1, 6.2, 6.3 on MCP architecture)
- **Vibe Trading Inventory**: `docs/vibe_trading_inventory.md` (Skills, tools, swarms, backtest engine)
- **Vibe Trading Porting Status**: `docs/vibe_trading_porting_complete.md` (83 skills ported)
- **Porting Status**: `docs/PORTING_STATUS.md` (Overall porting progress)

---

**End of Document**
