# 01 — Architecture Research & Alignment

> **Status:** Final — decisions confirmed and implemented.
> **Created:** 2026-04-10
> **Last updated:** 2026-04-10

---

## 1. What We Learned from Research

### 1.1 Hermes Agent (NousResearch) — 44.6k ⭐

Hermes is a **self-improving CLI/cloud agent** built around a learning loop. Relevant internals:

| Component | What it does | Reuse value for Motis |
|---|---|---|
| **Skills system** | Agent creates & improves Python scripts from experience; stored in `~/.hermes/skills/` | **Operator slot** sits at this same layer — we extend the skill model |
| **Memory (Honcho)** | Long-term user memory with `MEMORY.md` / `USER.md` | Per-user memory for strategy context ✅ |
| **Toolsets** | Swappable tool bundles exposed to the model | MCP tools mount here |
| **Agentic loop** | ReAct-style loop with context compression & trajectory storage | Master agent backbone ✅ |
| **Gateway** | Telegram, Discord, Slack, Signal bridges | Future mobile/notification layer |
| **MCP support** | `mcp_serve.py` — Hermes can act as MCP server OR consume MCPs | Key integration point with Vibe-Trading |
| **ACP adapter** | Agent Communication Protocol adapter | Potential basis for operator↔coordinator messaging |
| **Cron** | Time-based task scheduling | Paper-trade / live-trade heartbeats |

**What Hermes does NOT give us:**
- Multi-user isolation (it's single-user CLI-first)
- LangGraph-style deterministic workflow nodes
- Exchange connectivity
- Web platform / auth / marketplace

**Decision:** Fork Hermes as the **Motis Agent core**. Keep its skill system, memory, agentic loop. Hermes is vendored at `services/agent/upstream/hermes/`.

---

### 1.2 Vibe-Trading (HKUDS) — 562 ⭐

A **ReAct agent with 68 finance skills and 29 swarm presets**, built on LangChain/LangGraph.

| Component | What it gives us |
|---|---|
| **68 skills (7 categories)** | Data sourcing (tushare, yfinance, OKX, AKShare, CCXT), technical analysis, SMC, Elliott Wave, ML strategies, options, DeFi, macro, fundamentals |
| **Swarm presets** | `investment_committee`, `crypto_trading_desk`, `quant_strategy_desk`, `risk_committee` — 29 presets of multi-agent debate teams |
| **Backtest engine** | Multi-market rules (equities, crypto, forex); Pine Script v6 export |
| **MCP server** | 16 tools exposed via stdio MCP — plug directly into Motis |
| **Data auto-fallback** | 5 sources, zero-config |
| **API server** | FastAPI, SSE events, session management |

**Decision:** Vendored at `services/agent/upstream/vibe_trading/`. Port selectively:
- Python signal engines → `skills/finance/` (85% copy-paste)
- SKILL.md files → system prompt context blocks (100% copy-paste)
- Backtest engines/loaders → `services/platform/operator_runtime/backtest/` (70% copy-paste)
- Swarm YAMLs → operator design templates (0% runnable, 100% design reference)

See [03-skill-integration.md](./03-skill-integration.md) for the full mapping.

---

### 1.3 Claude Managed Agents (Anthropic, April 8 2026)

Anthropic's hosted agent execution platform:
- **Sandboxed execution**, checkpointing, credential management, scoped permissions, end-to-end tracing
- **Multi-agent coordination** (limited research preview)
- **Pricing:** Token cost + $0.08/session-hour active runtime

| Factor | Analysis |
|---|---|
| **Vendor lock-in** | Medium-high. Logic defined in Anthropic's YAML/NL format |
| **Model flexibility** | Locked to Claude — Hermes supports 200+ models via OpenRouter |
| **Customization** | Limited execution env control; can't deep-customize operator graph |
| **Cold-start simplicity** | Very fast prototype — managed infra, no k8s needed |
| **Cost at scale** | $0.08/session-hr × many concurrent operators = expensive |
| **Competition arena** | Would need custom coordination layer on top anyway |

**Decision:** **Optional execution backend**, not core foundation. Operators define their
LangGraph workflow in our own format. When deploying, the user can choose execution backend:
- `local` — runs on Motis cloud infra (FastAPI + Celery workers)
- `claude_managed` — serializes the operator as a Claude-compatible agent spec
- `modal` / `fly.io` — serverless for burstable workloads

---

## 2. The Operator Concept

```
User ──NL chat──► Master Agent (Motis / Hermes core)
                     │
                     ├─ Skills (one-shot callable functions)
                     │     └─ e.g., "fetch BTC price", "calculate RSI"
                     │
                     ├─ Operators (LangGraph StateGraph workflows)
                     │     ├─ ResearchOperator (market scan → debate → synthesis)
                     │     ├─ BacktestOperator (parse → data → engine → metrics)
                     │     ├─ PaperTradeOperator (signal → risk → paper exec → track)
                     │     └─ LiveTradeOperator (signal → risk → exchange → monitor)
                     │
                     └─ Tools (web, terminal, memory, delegation)
```

**Key decisions (confirmed):**

1. **Operator = LangGraph StateGraph** with named nodes. Model reasoning only at specific nodes.
2. **Operators are autonomous agents** — they can run independently of the platform.
3. **Risk management is baked into operator code**, not injected by the platform.
4. **Quality Gate** validates operator safety before deployment (10-point checklist).
5. **Operators are versioned** — rollback at any time.
6. **Operators are shareable** — the Marketplace uploads the operator spec (without API keys).

See [02-operator-system.md](./02-operator-system.md) for the complete design.

---

## 3. Infrastructure Architecture

### 3.1 System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         MOTIS PLATFORM                              │
│                                                                     │
│  ┌──────────┐    ┌─────────────────────────────────────────────┐  │
│  │ Next.js  │    │           API Gateway (FastAPI)              │  │
│  │Frontend  │◄──►│  Auth (JWT/Supabase) · Rate Limit · Router  │  │
│  └──────────┘    └──────────┬──────────────────────────────────┘  │
│                              │                                      │
│             ┌────────────────▼──────────────────┐                  │
│             │        Agent Service                │                  │
│             │  (Hermes fork — multi-user)         │                  │
│             │  ┌────────────┐ ┌────────────────┐ │                  │
│             │  │ Per-User   │ │ Operator       │ │                  │
│             │  │ Context DB │ │ Registry       │ │                  │
│             │  └────────────┘ └────────────────┘ │                  │
│             └────────┬───────────────────────────┘                  │
│                      │  MCP calls                                   │
│         ┌────────────▼─────────────────────┐                       │
│         │        Motis MCP Server           │                       │
│         │  ┌──────────┐ ┌───────────────┐  │                       │
│         │  │ Trading  │ │ Research/BT   │  │                       │
│         │  │ Exec MCP │ │ (Vibe-Trading │  │                       │
│         │  │          │ │  MCP proxy)   │  │                       │
│         │  └──────────┘ └───────────────┘  │                       │
│         └──────────────────────────────────┘                       │
│                                                                     │
│    ┌──────────────────────────────────────────────────────────┐    │
│    │                  Operator Runtime                          │    │
│    │  Celery Workers · Redis State Store · Beat Scheduler      │    │
│    └───────────────────┬──────────────────────────────────────┘    │
│                         │                                           │
│    ┌────────────────────▼──────────────────────────────┐          │
│    │                  Data Layer                         │          │
│    │  PostgreSQL (Supabase)  ·  Redis  ·  S3/R2         │          │
│    └────────────────────────────────────────────────────┘          │
│                                                                     │
│    ┌────────────────────────────────────────────────────┐          │
│    │               External Services                      │          │
│    │  Hyperliquid · Binance · CCXT exchanges              │          │
│    │  Stripe (billing) · Hermes Gateway (messaging)       │          │
│    └────────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────────┘
```

### 3.2 Per-User Agent Isolation

```python
# Each API request resolves to a scoped UserContext
class UserContext:
    user_id: str
    memory: MemoryManager          # PostgreSQL-backed (platform) or SQLite (CLI)
    skills: SkillRegistry          # per-user skills + finance skills
    operators: OperatorService     # per-user operators
    session: ConversationSession   # Redis-cached, DB-persisted
```

### 3.3 Dual Runtime Model

Operators run in two modes with identical code:

| | Platform Mode | Standalone CLI Mode |
|---|---|---|
| **State persistence** | Redis | Local SQLite |
| **Scheduling** | Celery Beat | `asyncio` loop |
| **log_event()** | Writes to `operator_run_logs` table | Writes to stdout |
| **submit_order()** | Goes through MCP risk layer | Direct exchange SDK |
| **Model calls** | User's BYOM config or platform default | Local API key |

The SDK functions abstract the difference — operator code doesn't know which mode it's in.

### 3.4 Key Technical Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Base agent framework | Fork Hermes | Mature agentic loop, memory, skills, gateway |
| 2 | Operator workflow engine | LangGraph | Consistent with Vibe-Trading, best Python DAG lib |
| 3 | Vibe-Trading integration | Vendor + selective port | MCP too heavy for latency-sensitive skills |
| 4 | Claude Managed Agents | Optional backend | Avoid lock-in, preserve model flexibility |
| 5 | Multi-user isolation | Thread + DB-scoped context | Simple, scales to ~100 concurrent users |
| 6 | Operator persistence | Redis + Celery | Simpler than Temporal; upgrade path exists |
| 7 | Auth | Supabase | DB + Auth + realtime in one |
| 8 | Frontend | Next.js | SSR for marketplace SEO |
| 9 | Agent streaming | SSE | Simpler than WebSocket for unidirectional |
| 10 | Exchange connectivity | MCP wrapping CCXT + exchange SDKs | Uniform tool interface |
