# Motis Data MCP Contracts

This document defines the target contract surface for `motis_data_mcp`.

It is intentionally contract-first:
- active tools are already exposed by the live MCP service
- planned tools are defined in code in `motis_data_mcp/tools.py` but are not yet exposed to live clients
- provider routing is free-first and structured-data-first

## Design Rules

- Numeric market, macro, flow, and panel data should come from structured adapters.
- `web_search`, `read_url`, `web_extract`, and `web_crawl` are for discovery, documents, filings text, policy releases, and narrative research.
- Skills should describe methodology, not hide the primary data-access path.
- Motis should prefer provider fallback chains over "just search the web" for anything that looks like a dataset.

## Active MCP Surface

These tools are live today:

| Domain | Tool |
|--------|------|
| Web | `web_search` |
| Web | `web_extract` |
| Web | `read_url` |
| Web | `web_fetch` |
| Web | `web_crawl` |
| Market | `market.resolve_symbol` |
| Market | `market.get_ohlcv` |
| Market | `market.get_ticker` |
| Market | `market.get_orderbook` |
| Market | `market.get_funding_rate` |
| Market | `market.get_open_interest` |
| Macro | `macro.get_series` |
| Equity | `equity.get_fundamentals` |
| Equity | `equity.get_earnings_calendar` |
| Flows | `flows.get_connect` |
| China | `china.get_moneyflow` |

The web tools are wired.
The market core is also wired now through free-first structured adapters:

- `market.resolve_symbol`
- `market.get_ohlcv`
- `market.get_ticker`
- `market.get_orderbook`
- `market.get_funding_rate`
- `market.get_open_interest`

Current provider routing:

- A-shares: `tushare -> akshare`
- US / HK equities: `yfinance -> akshare`
- Crypto spot / perp: `okx -> ccxt`

The first structured research slice is also live:

- `macro.get_series`
- `equity.get_fundamentals`
- `equity.get_earnings_calendar`
- `flows.get_connect`
- `china.get_moneyflow`

Current provider routing:

- US macro: `fred`
- China macro: `akshare`
- US / HK equity fundamentals and earnings: `yfinance -> tushare`
- Connect flows and A-share moneyflow: `tushare`

The rest of the contract inventory below remains planned.

## Planned Contract Inventory

These tools are defined in `PLANNED_DATA_TOOLS` inside [tools.py](./motis_data_mcp/tools.py) and are the contract inventory we plan to graduate into the live MCP surface domain by domain.

### Market

- `market.list_instruments`
- `market.get_trades`
- `market.get_options_chain`
- `market.get_corporate_actions`

### Macro

- `macro.get_release_calendar`
- `macro.get_policy_doc`
- `macro.get_curve_snapshot`

### Equity and Flows

- `equity.get_filings`
- `equity.get_estimates`
- `equity.get_holders`
- `flows.get_etf`
- `flows.get_fund_flows`

### China-Specific

- `china.get_margin_financing`
- `china.get_sector_breadth`
- `china.get_property_hf`
- `china.get_rates`
- `china.get_lgfv_spreads`

### Crypto

- `crypto.get_onchain_metrics`
- `crypto.get_exchange_flows`
- `crypto.get_stablecoin_flows`
- `crypto.get_defi_tvl`
- `crypto.get_token_unlocks`
- `crypto.get_liquidations`

### Credit

- `credit.get_spreads`
- `credit.get_curve`
- `credit.get_issuer_metrics`
- `credit.get_rating_events`

### Commodity and Logistics

- `commodity.get_inventory`
- `commodity.get_supply_demand`
- `commodity.get_shipping_rates`
- `commodity.get_energy_balance`

### Quant Datasets

- `dataset.get_price_panel`
- `dataset.get_return_panel`
- `dataset.get_factor_panel`
- `dataset.get_event_panel`

## Provider Routing Plan

The routing plan is defined in `DATA_PROVIDER_ROUTING_PLAN` in [tools.py](./motis_data_mcp/tools.py).

### Structured Market Routing

| Market | Primary | Fallback |
|--------|---------|----------|
| A-shares | `tushare` | `akshare` |
| US equities | `yfinance` | `akshare` |
| HK equities | `yfinance` | `akshare` |
| Crypto | `okx` | `ccxt` |
| Futures | `tushare` | `akshare` |
| Funds | `tushare` | `akshare` |
| Macro | `akshare` | `tushare` |
| Forex | `akshare` | `yfinance` |

This routing plan is borrowed from the strongest part of the upstream Vibe Trading design:
detect the market, normalize the symbol, and fall back within the same market family rather than degrading straight into web scraping.

### Document and Web Routing

| Use case | Tool path |
|----------|-----------|
| Search and discovery | `web_search` |
| Read a single page | `read_url` / `web_fetch` |
| Read several pages | `web_extract` |
| Site map / crawl | `web_crawl` |

## Rollout Order

### Phase 1: Market Core

Status: shipped in the MCP.

- `market.get_ohlcv`
- `market.get_ticker`
- `market.get_orderbook`
- `market.resolve_symbol`
- `market.get_funding_rate`
- `market.get_open_interest`

This is the minimum slice that gives Motis a real structured market-data path instead of pretending it has live trading data.

### Phase 2: Research-Critical Structured Data

Status: initial slice shipped.

- `macro.get_series`
- `equity.get_fundamentals`
- `equity.get_earnings_calendar`
- `flows.get_connect`
- `china.get_moneyflow`

Still pending in this phase:

- remaining `macro.*`
- remaining `equity.*`
- remaining `flows.*`
- remaining `china.*`

This is what closes the gap for macro desks, equity research, ETF flow work, earnings prep, and China-specific workflows.

### Phase 3: Crypto and Credit Expansion

- `crypto.*`
- `credit.*`
- `commodity.*`

This covers on-chain, derivatives, fixed income, shipping, and geopolitical-energy workflows.

### Phase 4: Quant Dataset Layer

- `dataset.get_price_panel`
- `dataset.get_return_panel`
- `dataset.get_factor_panel`
- `dataset.get_event_panel`

This is what makes `factor_analysis` and `backtest` feel native instead of file-shuffling.

## Operator Mapping Summary

The builtin desks imply the following data priorities:

- Macro desks need `macro.*`, `china.*`, and policy documents.
- Global equity desks need `equity.*`, `flows.*`, and `market.*`.
- Crypto desks need `market.*`, `crypto.*`, and selected web/document access.
- Credit desks need `credit.*`, `china.*`, and `macro.*`.
- Commodity and geopolitical desks need `commodity.*`, `macro.*`, and web/document access.
- Quant desks need `market.*` plus `dataset.*`.

## Important Runtime Decision

The planned contracts are still not part of the live `DATA_TOOLS` export.

That is deliberate.

We want the contract inventory committed in code now, without immediately surfacing a large set of `not_implemented` tools to live agent runtimes. As each adapter becomes real, we move that contract from `PLANNED_DATA_TOOLS` into `ACTIVE_DATA_TOOLS`.
