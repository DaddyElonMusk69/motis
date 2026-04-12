# Vibe Trading Upstream Inventory

**Source:** `services/agent/upstream/vibe_trading/`  
**License:** MIT  
**Purpose:** Comprehensive categorization of Vibe Trading components for selective porting into MOTIS

---

## Executive Summary

Vibe Trading provides:
- **64 Skills** organized in 8 categories (data, technical, quant, fundamental, macro, multi-asset, strategy, utilities)
- **29 Swarm Presets** for multi-agent research teams
- **Backtest Engine** with 4 market-specific engines, 5 data loaders, 4 portfolio optimizers
- **19 Tools** including pattern recognition, factor analysis, options pricing, swarm orchestration
- **MCP Server** exposing 16 tools over HTTP

---

## 1. Skills Inventory (64 Total)

Skills are markdown-based prompts (`SKILL.md`) with optional Python signal engines (`example_signal_engine.py`).

### 1.1 Data Sources (6 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `ccxt` | 100+ crypto exchanges via CCXT | No | High |
| `yfinance` | US/HK stocks, ETFs via Yahoo Finance | No | High |
| `akshare` | A-shares, US, HK, futures, macro (free) | No | High |
| `tushare` | A-shares, funds, futures (requires token) | No | Medium |
| `okx-market` | OKX exchange crypto data | No | Medium |
| `data-routing` | Auto-fallback decision tree across sources | No | **Critical** |

**Porting Notes:**
- `data-routing` is the orchestration layer — port first
- CCXT, yfinance, akshare are already referenced in MOTIS PRD
- Tushare requires API token (China-specific)

---

### 1.2 Technical Analysis (9 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `technical-basic` | MA, MACD, RSI, Bollinger, volume | Yes | High |
| `candlestick` | Japanese candlestick patterns | Yes | High |
| `smc` | Smart Money Concepts (BOS, ChoCH, FVG, OB) | Yes | **Critical** |
| `ichimoku` | Ichimoku cloud system | Yes | Medium |
| `elliott-wave` | Elliott Wave pattern recognition | Yes | Medium |
| `harmonic` | Harmonic patterns (Gartley, Butterfly, etc.) | Yes | Medium |
| `chanlun` | Chan Lun (缠论) Chinese technical analysis | Yes | Low |
| `volatility` | ATR, Bollinger width, Keltner channels | Yes | High |
| `minute-analysis` | Intraday minute-level analysis | Yes | Medium |

**Porting Notes:**
- `smc` is already implemented in MOTIS (`services/agent/motis_agent/skills/finance/analysis/smc.py`)
- `technical-basic`, `candlestick`, `volatility` are high-value for operator signal generation
- Elliott Wave and Harmonic are complex — lower priority

---

### 1.3 Quantitative Analysis (7 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `factor-research` | Alpha factor construction framework | No | High |
| `ml-strategy` | ML-based strategy generation | No | Medium |
| `multi-factor` | Multi-factor model construction | Yes | High |
| `quant-statistics` | Statistical tests, cointegration, stationarity | No | High |
| `pair-trading` | Pairs trading signal generation | Yes | Medium |
| `correlation-analysis` | Cross-asset correlation analysis | No | High |
| `seasonal` | Seasonal pattern detection | Yes | Medium |

**Porting Notes:**
- `factor-research` and `multi-factor` are core for quant operators
- `quant-statistics` provides statistical rigor for backtests
- `correlation-analysis` is critical for portfolio operators

---

### 1.4 Fundamental & Valuation (6 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `financial-statement` | Financial statement analysis | No | High |
| `edgar-sec-filings` | SEC filings parser (10-K, 10-Q, 8-K) | No | Medium |
| `earnings-forecast` | Earnings forecast models | No | Medium |
| `earnings-revision` | Analyst earnings revision tracking | No | Medium |
| `fundamental-filter` | Fundamental screening (PE, PB, ROE, etc.) | Yes | High |
| `valuation-model` | DCF, DDM, multiples valuation | No | High |

**Porting Notes:**
- `financial-statement` and `valuation-model` are essential for equity operators
- `edgar-sec-filings` is US-specific but valuable for fundamental research
- `fundamental-filter` has a signal engine — good for screening operators

---

### 1.5 Macro & Research (10 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `global-macro` | Global macro analysis framework | No | High |
| `macro-analysis` | Macro indicator analysis (GDP, CPI, rates) | No | High |
| `geopolitical-risk` | Geopolitical risk assessment | No | Medium |
| `onchain-analysis` | Blockchain on-chain metrics | No | High |
| `crypto-derivatives` | Crypto derivatives analysis | No | High |
| `perp-funding-basis` | Perpetual funding rate & basis analysis | No | **Critical** |
| `defi-yield` | DeFi yield farming analysis | No | Medium |
| `stablecoin-flow` | Stablecoin flow tracking | No | High |
| `liquidation-heatmap` | Liquidation cluster mapping | No | High |
| `token-unlock-treasury` | Token unlock & treasury tracking | No | Medium |

**Porting Notes:**
- Crypto-specific skills (`perp-funding-basis`, `liquidation-heatmap`, `stablecoin-flow`, `onchain-analysis`) are high-value for crypto operators
- `global-macro` and `macro-analysis` are essential for macro-aware operators
- These are mostly research-oriented (no signal engines) — used in ResearchOperators

---

### 1.6 Multi-Asset & Cross-Market (12 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `etf-analysis` | ETF structure & flow analysis | No | Medium |
| `us-etf-flow` | US ETF flow tracking | No | Medium |
| `sector-rotation` | Sector rotation signals | No | Medium |
| `asset-allocation` | Portfolio allocation framework | No | High |
| `fund-analysis` | Mutual fund analysis | No | Low |
| `commodity-analysis` | Commodity market analysis | No | Medium |
| `credit-analysis` | Credit market analysis | No | Medium |
| `convertible-bond` | Convertible bond analysis | No | Low |
| `options-payoff` | Options payoff diagram generation | No | High |
| `options-advanced` | Advanced options strategies | No | High |
| `options-strategy` | Options strategy selection | No | High |
| `hedging-strategy` | Portfolio hedging strategies | No | High |

**Porting Notes:**
- Options skills (`options-payoff`, `options-advanced`, `options-strategy`) are valuable for derivatives operators
- `asset-allocation` and `hedging-strategy` are critical for portfolio-level operators
- `sector-rotation` is useful for equity rotation strategies

---

### 1.7 Strategy & Reporting (6 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `strategy-generate` | Strategy documentation generator | No | High |
| `report-generate` | Research report generator | No | High |
| `pine-script` | TradingView Pine Script v6 exporter | No | Medium |
| `backtest-diagnose` | Backtest failure diagnosis | No | High |
| `execution-model` | Execution cost modeling | No | High |
| `performance-attribution` | Performance attribution analysis | No | High |

**Porting Notes:**
- `strategy-generate` and `report-generate` are meta-skills for operator documentation
- `backtest-diagnose` is critical for BacktestOperator AI critique node
- `execution-model` is important for live trading operators
- `pine-script` enables TradingView export (PRD requirement)

---

### 1.8 Alternative Data & Sentiment (5 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `sentiment-analysis` | News & social sentiment analysis | No | High |
| `social-media-intelligence` | Social media signal extraction | No | Medium |
| `behavioral-finance` | Behavioral finance patterns | No | Medium |
| `event-driven` | Event-driven strategy framework | No | Medium |
| `corporate-events` | Corporate event tracking (M&A, splits, etc.) | No | Medium |

**Porting Notes:**
- `sentiment-analysis` is high-value for sentiment-driven operators
- `event-driven` and `corporate-events` are useful for event-based strategies

---

### 1.9 Regional/Specialized (3 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `adr-hshare` | ADR/H-share arbitrage | No | Low |
| `hk-connect-flow` | Hong Kong Connect flow tracking | No | Low |
| `market-microstructure` | Market microstructure analysis | No | Medium |
| `regulatory-knowledge` | Regulatory compliance knowledge | No | Low |
| `risk-analysis` | Risk metrics & VaR calculation | No | **Critical** |

**Porting Notes:**
- `risk-analysis` is critical for all operators (risk guard, position sizing)
- `market-microstructure` is valuable for execution quality
- Regional skills (ADR, HK Connect) are low priority unless targeting those markets

---

### 1.10 Utilities (2 skills)

| Skill | Description | Has Signal Engine | Priority |
|-------|-------------|-------------------|----------|
| `doc-reader` | Document reader (PDF, DOCX) | No | Low |
| `web-reader` | Web page content extraction | No | Low |

**Porting Notes:**
- Already have equivalents in Hermes (`web_tools.py`)
- Low priority for porting

---

## 2. Swarm Presets Inventory (29 Total)

Swarm presets are YAML configurations defining multi-agent research teams. Each preset has:
- Named agents with specific roles
- System prompts with analysis frameworks
- Task dependencies (parallel or sequential)
- Required variables (target, timeframe, market, etc.)

### 2.1 Crypto-Focused Swarms (4)

| Preset | Agents | Focus | Priority |
|--------|--------|-------|----------|
| `crypto_trading_desk` | Funding/Basis Analyst, Liquidation Analyst, Flow Analyst, Risk Manager | Execution-oriented crypto trading | **Critical** |
| `crypto_research_lab` | On-chain Analyst, Derivatives Analyst, Sentiment Analyst, Synthesizer | Crypto research & thesis generation | High |
| `statistical_arbitrage_desk` | Pairs Analyst, Mean Reversion Analyst, Cointegration Analyst, Risk Manager | Stat arb strategies | Medium |
| `derivatives_strategy_desk` | Options Strategist, Futures Analyst, Volatility Trader, Risk Manager | Derivatives strategies | Medium |

---

### 2.2 Equity-Focused Swarms (6)

| Preset | Agents | Focus | Priority |
|--------|--------|-------|----------|
| `investment_committee` | Bull Advocate, Bear Advocate, Risk Officer, Portfolio Manager | Long-short debate → final decision | **Critical** |
| `equity_research_team` | Fundamental Analyst, Technical Analyst, Valuation Analyst, Synthesizer | Equity deep-dive research | High |
| `fundamental_research_team` | Financial Statement Analyst, Industry Analyst, Valuation Analyst, Synthesizer | Fundamental analysis | High |
| `earnings_research_desk` | Earnings Analyst, Revision Tracker, Event Analyst, Synthesizer | Earnings-driven research | Medium |
| `sector_rotation_team` | Sector Analyst, Macro Analyst, Flow Analyst, Rotation Strategist | Sector rotation signals | Medium |
| `global_equities_desk` | US Analyst, Europe Analyst, Asia Analyst, Global Strategist | Global equity allocation | Medium |

---

### 2.3 Quant-Focused Swarms (4)

| Preset | Agents | Focus | Priority |
|--------|--------|-------|----------|
| `factor_research_committee` | Alpha Factor Researcher, Risk Factor Analyst, Backtest Engineer, Synthesizer | Factor research & validation | High |
| `quant_strategy_desk` | Quant Researcher, Backtest Engineer, Risk Analyst, Strategy PM | Quant strategy development | High |
| `ml_quant_lab` | ML Engineer, Feature Engineer, Backtest Validator, Production Engineer | ML-based strategies | Medium |
| `pairs_research_lab` | Pairs Screener, Cointegration Analyst, Backtest Engineer, Risk Manager | Pairs trading research | Medium |

---

### 2.4 Macro & Multi-Asset Swarms (5)

| Preset | Agents | Focus | Priority |
|--------|--------|-------|----------|
| `macro_rates_fx_desk` | Rates Analyst, FX Analyst, Macro Strategist, Risk Manager | Macro/rates/FX trading | High |
| `macro_strategy_forum` | Macro Analyst, Geopolitical Analyst, Policy Analyst, Strategist | Macro thesis generation | Medium |
| `global_allocation_committee` | Equity Allocator, Fixed Income Allocator, Alternative Allocator, CIO | Global asset allocation | Medium |
| `commodity_research_team` | Supply Analyst, Demand Analyst, Macro Analyst, Commodity Strategist | Commodity analysis | Medium |
| `geopolitical_war_room` | Geopolitical Analyst, Risk Analyst, Scenario Planner, Strategist | Geopolitical risk assessment | Low |

---

### 2.5 Portfolio & Risk Swarms (4)

| Preset | Agents | Focus | Priority |
|--------|--------|-------|----------|
| `risk_committee` | Market Risk Officer, Credit Risk Officer, Liquidity Risk Officer, CRO | Risk review & approval | High |
| `portfolio_review_board` | Performance Analyst, Attribution Analyst, Risk Analyst, PM | Portfolio review & optimization | Medium |
| `etf_allocation_desk` | ETF Screener, Flow Analyst, Sector Analyst, Allocation Strategist | ETF-based allocation | Low |
| `fund_selection_panel` | Fund Analyst, Performance Analyst, Risk Analyst, Selection Committee | Fund selection | Low |

---

### 2.6 Specialized Swarms (6)

| Preset | Agents | Focus | Priority |
|--------|--------|-------|----------|
| `technical_analysis_panel` | Trend Analyst, Pattern Analyst, Momentum Analyst, Synthesizer | Multi-method technical confluence | High |
| `sentiment_intelligence_team` | News Analyst, Social Media Analyst, Positioning Analyst, Synthesizer | Sentiment aggregation | Medium |
| `social_alpha_team` | Social Media Analyst, Influencer Tracker, Sentiment Analyst, Alpha Extractor | Social media alpha | Low |
| `event_driven_task_force` | Event Screener, Impact Analyst, Timing Analyst, Event Strategist | Event-driven strategies | Medium |
| `credit_research_team` | Credit Analyst, Spread Analyst, Default Risk Analyst, Credit Strategist | Credit analysis | Low |
| `convertible_bond_team` | Convertible Analyst, Equity Analyst, Credit Analyst, Arb Strategist | Convertible bond arbitrage | Low |

---

## 3. Backtest Engine Inventory

### 3.1 Engines (4)

| Engine | Markets | Features | Priority |
|--------|---------|----------|----------|
| `crypto.py` | Crypto spot & perps | Funding rate, slippage, fees | **Critical** |
| `global_equity.py` | US, HK, global equities | Commission, slippage, dividends | High |
| `china_a.py` | A-shares | T+1 settlement, stamp tax, commission | Medium |
| `options_portfolio.py` | Options | Greeks, IV, multi-leg strategies | Medium |

---

### 3.2 Data Loaders (5)

| Loader | Source | Markets | Priority |
|--------|--------|---------|----------|
| `ccxt_loader.py` | CCXT | 100+ crypto exchanges | **Critical** |
| `yfinance_loader.py` | Yahoo Finance | US, HK stocks, ETFs | High |
| `akshare_loader.py` | AKShare | A-shares, US, HK, futures, macro | High |
| `tushare.py` | Tushare | A-shares, funds, futures | Medium |
| `okx.py` | OKX | OKX exchange crypto | Medium |

**Porting Notes:**
- All loaders implement a common `BaseLoader` interface
- Auto-fallback logic is in `registry.py`
- CCXT, yfinance, akshare are the core three

---

### 3.3 Portfolio Optimizers (4)

| Optimizer | Method | Use Case | Priority |
|-----------|--------|----------|----------|
| `risk_parity.py` | Risk parity allocation | Equal risk contribution | High |
| `mean_variance.py` | Markowitz mean-variance | Return/risk optimization | High |
| `equal_volatility.py` | Equal volatility weighting | Volatility-balanced portfolio | Medium |
| `max_diversification.py` | Maximum diversification | Correlation-based diversification | Medium |

**Porting Notes:**
- Used for multi-asset portfolio operators
- All implement `BaseOptimizer` interface

---

### 3.4 Metrics (`metrics.py`)

Provides:
- Sharpe ratio, Sortino ratio, Calmar ratio
- Max drawdown, max drawdown duration
- Win rate, profit factor
- Total return, annualized return
- Volatility, downside deviation

**Priority:** **Critical** (used by BacktestOperator)

---

### 3.5 Runner (`runner.py`)

Orchestrates:
- Strategy parsing (from config.json)
- Data loading (via loader registry)
- Engine selection (by market type)
- Metrics calculation
- Report generation

**Priority:** **Critical** (core of BacktestOperator)

---

## 4. Tools Inventory (19 Total)

### 4.1 High-Priority Tools (Port to MOTIS)

| Tool | File | Description | Size | Target |
|------|------|-------------|------|--------|
| `pattern_tool` | `pattern_tool.py` | Candlestick + harmonic pattern detection | 16KB | `skills/finance/analysis/patterns.py` |
| `factor_analysis_tool` | `factor_analysis_tool.py` | Alpha factor computation | 12KB | `skills/finance/analysis/factor.py` |
| `options_pricing_tool` | `options_pricing_tool.py` | Black-Scholes + Greeks | 8KB | `skills/finance/analysis/options.py` |
| `swarm_tool` | `swarm_tool.py` | Swarm orchestration | 20KB | Adapt into `ResearchOperator` |
| `backtest_tool` | `backtest_tool.py` | Backtest trigger | 6KB | Adapt into `BacktestOperator` |

---

### 4.2 Medium-Priority Tools

| Tool | File | Description | Notes |
|------|------|-------------|-------|
| `subagent_tool` | `subagent_tool.py` | Single sub-agent delegation | Similar to Hermes `delegate_tool` |
| `load_skill_tool` | `load_skill_tool.py` | Dynamic skill loading | Useful for skill registry |
| `compact_tool` | `compact_tool.py` | Context compression | Similar to Hermes compression |
| `task_tools` | `task_tools.py` | Task management | Low priority |
| `background_tools` | `background_tools.py` | Background task execution | Low priority |

---

### 4.3 Low-Priority Tools (Already Have Equivalents)

| Tool | File | Reason |
|------|------|--------|
| `bash_tool` | `bash_tool.py` | Have `terminal.py` (safer sandbox) |
| `web_reader_tool` | `web_reader_tool.py` | Have `web.py` with Brave/Tavily |
| `web_search_tool` | `web_search_tool.py` | Have `web.py` with Brave/Tavily |
| `doc_reader_tool` | `doc_reader_tool.py` | Low priority for Phase 0-1 |
| `read_file_tool` | `read_file_tool.py` | Have file system tools |
| `write_file_tool` | `write_file_tool.py` | Have file system tools |
| `edit_file_tool` | `edit_file_tool.py` | Have file system tools |

---

## 5. MCP Server (`mcp_server.py`)

Exposes 16 MCP tools over HTTP:
- `backtest` — trigger backtest
- `factor_analysis` — compute alpha factors
- `options_pricing` — Black-Scholes + Greeks
- `pattern_recognition` — candlestick + harmonic patterns
- `swarm_run` — spawn research swarm
- `load_skill` — dynamic skill loading
- `read_file`, `write_file`, `edit_file` — file operations
- `bash` — shell execution
- `web_search`, `web_reader` — web tools
- `doc_reader` — document parsing
- `subagent` — sub-agent delegation
- `compact` — context compression
- `task_*` — task management

**Porting Notes:**
- Some tools should be added to the split MCP boundary under `services/mcp/` (most likely `motis_data_mcp/` for read-only data tools)
- Others are redundant with Hermes tools
- Swarm orchestration should be native (not MCP) per PRD

---

## 6. Agent Core (DO NOT PORT)

Files in `agent/src/agent/`:
- `loop.py` — single-agent ReAct loop
- `skills.py` — dynamic SKILL.md loader
- `memory.py` — local file-based conversation memory
- `context.py` — session context
- `tools.py` — tool wiring

**Reason:** Already superseded by Hermes-based `MotisAgentLoop` (multi-user, DB-backed, SSE streaming)

---

## 7. Porting Priority Matrix

### Phase 0 (Foundation) — Immediate

| Component | Source | Target | Reason |
|-----------|--------|--------|--------|
| Data routing skill | `skills/data-routing/` | `skills/finance/data/routing.py` | **Already done** per PRD |
| SMC skill | `skills/smc/` | `skills/finance/analysis/smc.py` | **Already done** per PRD |
| Backtest engine | `backtest/` | `operator_runtime/backtest/` | Core for BacktestOperator |
| Swarm presets | `config/swarm/*.yaml` | `swarms/presets/` | Core for ResearchOperator |
| Pattern tool | `tools/pattern_tool.py` | `skills/finance/analysis/patterns.py` | High-value signal generation |

---

### Phase 1 (Operators) — Next

| Component | Source | Target | Reason |
|-----------|--------|--------|--------|
| Factor analysis tool | `tools/factor_analysis_tool.py` | `skills/finance/analysis/factor.py` | Quant operator signals |
| Options pricing tool | `tools/options_pricing_tool.py` | `skills/finance/analysis/options.py` | Derivatives operators |
| Technical skills | `skills/technical-basic/`, `candlestick/`, `volatility/` | `skills/finance/analysis/` | Signal generation |
| Risk analysis skill | `skills/risk-analysis/` | `skills/finance/analysis/risk.py` | Risk guard, position sizing |
| Crypto skills | `skills/perp-funding-basis/`, `liquidation-heatmap/`, `stablecoin-flow/` | `skills/finance/research/` | Crypto operator research |

---

### Phase 2 (Marketplace) — Later

| Component | Source | Target | Reason |
|-----------|--------|--------|--------|
| Quant skills | `skills/factor-research/`, `multi-factor/`, `quant-statistics/` | `skills/finance/analysis/` | Advanced quant operators |
| Fundamental skills | `skills/financial-statement/`, `valuation-model/`, `fundamental-filter/` | `skills/finance/analysis/` | Equity operators |
| Strategy skills | `skills/strategy-generate/`, `backtest-diagnose/`, `performance-attribution/` | `skills/finance/reporting/` | Operator documentation |
| Remaining swarms | All 29 presets | `swarms/presets/` | Full research coverage |

---

## 8. Skills with Signal Engines (14 Total)

These skills include `example_signal_engine.py` — deterministic Python implementations suitable for operator nodes:

1. `candlestick` — Japanese candlestick patterns
2. `chanlun` — Chan Lun (缠论) analysis
3. `elliott-wave` — Elliott Wave patterns
4. `fundamental-filter` — Fundamental screening
5. `harmonic` — Harmonic patterns
6. `ichimoku` — Ichimoku cloud
7. `minute-analysis` — Intraday analysis
8. `multi-factor` — Multi-factor models
9. `pair-trading` — Pairs trading signals
10. `seasonal` — Seasonal patterns
11. `smc` — Smart Money Concepts (already ported)
12. `technical-basic` — Basic technical indicators
13. `volatility` — Volatility indicators

**Porting Strategy:**
- Extract signal engines into `skills/finance/analysis/` as standalone functions
- Keep SKILL.md as documentation/context for the Master Agent
- Signal engines can be called directly by operator nodes (no LLM reasoning needed)

---

## 9. Key Architectural Insights

### 9.1 Skill Structure

```
skills/<skill-name>/
├── SKILL.md                    # LLM-readable prompt (loaded by agent)
├── example_signal_engine.py    # Deterministic Python (optional)
└── references/                 # Documentation (optional)
```

**Usage:**
- Master Agent loads `SKILL.md` into context when skill is referenced
- Operator nodes call `example_signal_engine.py` functions directly (no LLM)

---

### 9.2 Swarm Structure

```yaml
name: swarm_name
title: "Human-Readable Title"
description: "What this swarm does"

agents:
  - id: agent_id
    role: Human-Readable Role
    system_prompt: |
      Multi-line prompt with {variables}
    tools: [bash, read_file, write_file, load_skill, ...]
    skills: [skill-name-1, skill-name-2, ...]
    max_iterations: 50
    timeout_seconds: 600

tasks:
  - id: task-1
    agent_id: agent_id
    prompt_template: "Task prompt with {variables}"
    depends_on: []
  
  - id: task-2
    agent_id: another_agent
    prompt_template: "Another task"
    depends_on: [task-1]
    input_from:
      previous_output: task-1

variables:
  - name: target
    description: "What this variable is"
    required: true
```

**Usage:**
- ResearchOperator loads a preset YAML
- Spawns N agents in parallel (or sequential based on `depends_on`)
- Each agent runs a full ReAct loop with its system prompt
- Results are synthesized by a final agent or node

---

### 9.3 Backtest Engine Structure

```python
# User writes config.json
{
  "strategy": "smc",
  "symbols": ["BTC-USDT"],
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "source": "auto",  # Auto-fallback
  "params": {"swing_length": 10}
}

# Runner orchestrates:
1. Parse config
2. Detect market type (crypto)
3. Select engine (crypto.py)
4. Select loader (ccxt_loader.py with fallback)
5. Load data
6. Run strategy
7. Calculate metrics
8. Generate report
```

**Porting:**
- Wrap this in `BacktestOperator` LangGraph nodes
- Add `ai_critique` node (model analyzes results, suggests improvements)
- Persist results to DB + S3

---

## 10. Licensing & Attribution

**License:** MIT  
**Source:** https://github.com/HKUDS/Vibe-Trading

**MIT License Requirements:**
- Preserve copyright notice in ported files
- Include LICENSE file reference
- Attribution in documentation

**Compliance:**
- Add header comment to all ported files:
  ```python
  # Adapted from Vibe-Trading (https://github.com/HKUDS/Vibe-Trading)
  # Original work licensed under MIT License
  # Copyright (c) 2024 HKUDS
  ```

---

## 11. Next Steps

1. **Phase 0 (Immediate):**
   - Verify SMC and data routing skills are correctly ported
   - Port backtest engine to `operator_runtime/backtest/`
   - Port 29 swarm presets to `swarms/presets/`
   - Port pattern tool to `skills/finance/analysis/patterns.py`

2. **Phase 1 (Operators):**
   - Port factor analysis and options pricing tools
   - Port technical skills (technical-basic, candlestick, volatility)
   - Port crypto research skills (funding, liquidation, stablecoin flow)
   - Port risk analysis skill

3. **Phase 2 (Marketplace):**
   - Port remaining quant and fundamental skills
   - Port strategy/reporting skills
   - Complete all 29 swarm presets

4. **Documentation:**
   - Create skill registry documentation
   - Document swarm preset usage
   - Create backtest engine API documentation

---

**End of Inventory**
