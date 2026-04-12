# MOTIS MCP Quick Reference

**Last Updated:** April 10, 2026

---

## TL;DR

**Recommendation**: Use **hybrid approach** for MOTIS MCP architecture:

1. **Market Data**: Use existing `doggybee/mcp-server-ccxt` (TypeScript, high-performance)
2. **Execution**: Build custom MOTIS MCP (Python, multi-user, risk guard)
3. **Operator Management**: Build custom MOTIS MCP (Python, CRUD/invocation)
4. **Skills/Swarms/Backtest**: Keep native (NOT MCP) per PRD

---

## Existing CCXT MCP Servers

### Option A: doggybee/mcp-server-ccxt ⭐ RECOMMENDED

- **Language**: TypeScript/Node.js
- **NPM**: `@mcpfun/mcp-server-ccxt`
- **Exchanges**: 20+ (Binance, Coinbase, Kraken, Bybit, OKX, etc.)
- **Features**: High-performance caching (LRU), adaptive rate limiting, proxy support
- **Tools**: 30+ (public + private APIs)
- **Pros**: Production-ready, well-maintained, comprehensive
- **Cons**: TypeScript (requires Node.js runtime)

**Installation**:
```bash
npm install -g @mcpfun/mcp-server-ccxt
mcp-server-ccxt
```

**Configuration**:
```json
{
  "mcpServers": {
    "ccxt": {
      "command": "mcp-server-ccxt"
    }
  }
}
```

---

### Option B: lazy-dinosaur/ccxt-mcp

- **Language**: Python
- **NPM**: `@lazydino/ccxt-mcp`
- **Exchanges**: 100+ via CCXT
- **Features**: Multi-account support, trading analytics, risk management
- **Pros**: Python (same as MOTIS), multi-account support
- **Cons**: Less performance optimization, still single-user design

**Installation**:
```bash
npm install -g @lazydino/ccxt-mcp
ccxt-mcp
```

---

## MOTIS MCP Architecture

```
Agent Service (Python)
    ↓ MCP calls
┌───────────────────────────────────────┐
│     MCP Server Layer (3 servers)      │
│                                       │
│  1. MOTIS Execution MCP (Python)      │
│     - execute_paper_trade             │
│     - execute_live_trade              │
│     - get_positions                   │
│     - get_account_balance             │
│     - Platform risk guard             │
│     - Multi-user auth                 │
│     - API key decryption              │
│     - Immutable trade_log             │
│                                       │
│  2. CCXT Market Data MCP (TypeScript) │
│     - Use doggybee/mcp-server-ccxt    │
│     - Public API only (no execution)  │
│     - get_ticker, get_orderbook, etc. │
│                                       │
│  3. MOTIS Operator MCP (Python)       │
│     - operator_create, update, delete │
│     - operator_invoke, status         │
│     - operator_pause, resume          │
│     - Multi-user scoped               │
└───────────────────────────────────────┘
```

---

## What Goes Where?

### Native Skills (NOT MCP) ✅

**Location**: `services/agent/motis_agent/skills/finance/`

- Data routing (auto-fallback across 5 sources)
- Technical analysis (SMC, candlestick, etc.)
- Quantitative analysis (factor, multi-factor)
- Fundamental analysis (financial statements, valuation)
- Macro research (global macro, on-chain)
- Crypto research (funding, liquidation, stablecoin flow)
- Reporting (strategy gen, backtest diagnose)

**Why Native?**
- Performance (no IPC overhead)
- Context sharing (access agent memory, user config)
- Simplicity (no MCP protocol overhead)
- Skill registry (auto-discovery)

---

### MCP Tools (External Process) ✅

**What Belongs Here**:
- Trading execution (risk guard, API key security, trade log)
- Market data (high-performance caching, rate limiting)
- Operator management (CRUD, state machine, runtime)
- External integrations (news APIs, SEC filings, on-chain data)

**Why MCP?**
- Security isolation (separate process)
- Multi-user support (authentication, user context)
- Extensibility (users can add custom MCP servers)
- Rate limiting (per-user rate limits)

---

## Implementation Checklist

### Phase 0: Foundation (Immediate)

- [ ] Deploy `doggybee/mcp-server-ccxt` as separate Node.js process
- [ ] Configure MOTIS Agent Service to call CCXT MCP
- [ ] Disable execution tools in CCXT MCP (public API only)
- [ ] Implement `execute_live_trade` in MOTIS Execution MCP
- [ ] Implement `get_positions` and `get_account_balance`
- [ ] Add platform risk guard checks
- [ ] Write fills to `trade_log` table
- [ ] Test: Agent → CCXT MCP → market data
- [ ] Test: Agent → MOTIS Execution MCP → paper trade

### Phase 1: Operators (Next)

- [ ] Implement MOTIS Operator MCP tools (CRUD, invoke, status)
- [ ] Integrate with Celery Beat (schedule operator ticks)
- [ ] Implement Quality Gate (5 blockers for paper, 10 for live)
- [ ] Test: Operator → MOTIS Execution MCP → live trade

### Phase 2: Marketplace (Later)

- [ ] Arena Service (read trade_log, compute leaderboard)
- [ ] Marketplace Service (publish, subscribe, revenue sharing)
- [ ] Fill Reconciler (cross-check trade_log vs. exchange)

---

## Security Checklist

- [ ] API keys encrypted at rest (AES-256)
- [ ] API keys decrypted only at MCP layer
- [ ] Operators cannot call exchange APIs directly
- [ ] Platform risk guard enforced before all trades
- [ ] Per-user risk limits stored in DB
- [ ] Global kill switch for emergency halt
- [ ] User context injection (operator_id → user_id)
- [ ] Database row-level security (PostgreSQL RLS)
- [ ] Audit log for all MCP calls

---

## Performance Checklist

- [ ] Market data caching (LRU, 10s TTL for tickers)
- [ ] Adaptive rate limiting (exponential backoff)
- [ ] Batch market data requests where possible
- [ ] MCP only for high-value, low-frequency calls
- [ ] Skills remain native (no IPC overhead)

---

## Key References

- **Full Strategy**: `docs/motis_mcp_strategy.md`
- **MOTIS PRD**: `docs/motis_prd.md` (Sections 5.1, 6.2, 6.3)
- **Vibe Trading Inventory**: `docs/vibe_trading_inventory.md`
- **Porting Status**: `docs/PORTING_STATUS.md`

---

## Quick Commands

### Deploy CCXT MCP (doggybee)
```bash
# Install globally
npm install -g @mcpfun/mcp-server-ccxt

# Start server
mcp-server-ccxt

# Or run without installation
npx @mcpfun/mcp-server-ccxt
```

### Test CCXT MCP
```bash
# In Claude Desktop config
{
  "mcpServers": {
    "ccxt": {
      "command": "mcp-server-ccxt"
    }
  }
}

# Test query
"What's the current price of Bitcoin on Binance?"
```

### Deploy MOTIS Execution MCP
```bash
# From services/mcp/
motis-execution-mcp
```

---

**End of Quick Reference**
