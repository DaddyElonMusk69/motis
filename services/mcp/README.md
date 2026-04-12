## MCP Layout

`services/mcp` is the Motis MCP workspace. It is a mono-repo for multiple
Motis-owned MCP services, not one giant mixed server.

Current structure:

- `motis_data_mcp/`
  - Read-only network and market data boundary
  - Owns the Motis networking contract for `web_search`, `web_extract`, `read_url`, `web_fetch`, and `web_crawl`
  - Also owns the provider-backed market core plus the first structured research-data slice for macro series, equity fundamentals, earnings calendars, connect flows, and China moneyflow
- `motis_execution_mcp/`
  - Trading execution boundary
  - Owns platform risk checks, exchange auth, and trade-log writes
- `motis_operator_mcp/`
  - Operator control plane
  - Owns operator CRUD, invocation, pause/resume, and status contracts

This replaces the old unified `motis_mcp/` package. We split services by trust
boundary and responsibility rather than by vendor or provider.

## Service Shape

Each MCP service should have the same basic shape:

- `server.py`
  - Native stdio MCP server for direct MCP clients
- `http_server.py`
  - HTTP wrapper for current platform-style service hosting
- `settings.py`
  - Service-local host, port, and auth configuration
- `tools.py`
  - Motis-owned tool contracts and dispatch boundary

That means all three services are now hostable in a consistent way, even if
their internal tool implementations are at different maturity levels.

## Networking Contract

`motis_data_mcp` now defines a Motis-owned networking interface so we can
replace Hermes-local web tools with MCP-backed equivalents without changing
the agent-facing tool surface.

Compatibility tool names:

- `web_search`
- `web_extract`
- `read_url`
- `web_fetch`
- `web_crawl`

Design principles:

- Tool names stay stable for the agent and existing prompts.
- Request and response envelopes are Motis-owned and provider-agnostic.
- Search, read, and crawl providers can be swapped independently.
- `web_search` now defaults to a Motis-native federated provider that fans out
  across DDG, Startpage, and Bing request adapters, then dedupes and reranks
  results before returning them.

Normalized envelope shape:

```json
{
  "status": "ok",
  "service": "motis_data_mcp",
  "tool": "web_search",
  "provider": "motis_search",
  "request_id": "mdmcp_123456abcdef",
  "as_of": "2026-04-11T12:34:56Z",
  "warnings": [],
  "error": null,
  "data": {
    "engines": ["ddg", "startpage", "bing"],
    "partial_failures": []
  }
}
```

Provider selection env vars:

- `MOTIS_WEB_SEARCH_PROVIDER`
- `MOTIS_WEB_SEARCH_ENGINES`
- `MOTIS_WEB_EXTRACT_PROVIDER`
- `MOTIS_WEB_CRAWL_PROVIDER`

Current state:

- The interface and provider router are implemented.
- Search defaults to a Motis-native federated provider with DDG, Startpage,
  and Bing engine adapters. Setting `MOTIS_WEB_SEARCH_PROVIDER=ddg` still
  forces the single-engine DDG path.
- URL extract and single-URL reads are wired to a Motis HTTP reader with basic SSRF protection.
- Crawl contract exists, but crawl provider wiring is still pending.
- The market core is now wired through structured fallback chains:
  - A-shares: `tushare -> yfinance -> akshare`
  - US / HK equities: `yfinance -> akshare`
  - Crypto: `okx -> ccxt`
- The first structured research-data slice is now live:
  - `macro.get_series`: `fred` for US, `akshare` for China
  - `equity.get_fundamentals`: A-shares `tushare -> yfinance`; US / HK `yfinance -> tushare`
  - `equity.get_earnings_calendar`: A-shares `tushare -> yfinance`; US / HK `yfinance -> tushare`
  - `flows.get_connect`: `tushare`
  - `china.get_moneyflow`: `tushare`

Data contract roadmap:

- See [MOTIS_DATA_MCP_CONTRACTS.md](./MOTIS_DATA_MCP_CONTRACTS.md) for the planned structured-data surface, provider fallback map, and rollout order.

## Hosted Transport

Today we support two transport modes:

- Native MCP over stdio
  - Used by direct MCP clients
  - Entry points: `motis-data-mcp`, `motis-execution-mcp`, `motis-operator-mcp`
- HTTP tool dispatch
  - Transitional hosted-service transport for the current Motis platform paths
  - Entry points: `motis-data-mcp-http`, `motis-execution-mcp-http`, `motis-operator-mcp-http`

Current auth/header contract for the HTTP wrappers:

- `X-Agent-Token`
- `X-User-Id`
- `X-Conversation-Id`

The extra headers are reserved for future per-user policy and audit wiring.

## Current Agent Integration

The current live `motis_agent` only directly calls the data service over the
HTTP compatibility path:

- `POST {DATA_MCP_URL}/tools/web_search`
- `POST {DATA_MCP_URL}/tools/read_url`
- `POST {DATA_MCP_URL}/tools/market.get_ohlcv`
- `POST {DATA_MCP_URL}/tools/market.get_ticker`
- `POST {DATA_MCP_URL}/tools/market.get_orderbook`
- `POST {DATA_MCP_URL}/tools/market.get_funding_rate`
- `POST {DATA_MCP_URL}/tools/market.get_open_interest`
- `POST {DATA_MCP_URL}/tools/macro.get_series`
- `POST {DATA_MCP_URL}/tools/equity.get_fundamentals`
- `POST {DATA_MCP_URL}/tools/equity.get_earnings_calendar`
- `POST {DATA_MCP_URL}/tools/flows.get_connect`
- `POST {DATA_MCP_URL}/tools/china.get_moneyflow`

Execution and operator MCP services now expose the same hosted-service shape,
but the agent has not yet been switched to consume them in the same way.

## Local Run Examples

This folder is runnable on its own. The standalone bootstrap installs the MCP
workspace package into `services/mcp/venv` and keeps its cache local to
`services/mcp/.uv-cache`.

Bootstrap once:

```bash
cd services/mcp
./setup-mcp.sh
```

Data MCP:

```bash
cd services/mcp
AGENT_MCP_SECRET=dev-secret-change-in-prod \
MOTIS_WEB_SEARCH_PROVIDER=federated \
./motis-mcp data-http
```

Execution MCP:

```bash
cd services/mcp
AGENT_MCP_SECRET=dev-secret-change-in-prod \
./motis-mcp execution-http
```

Operator MCP:

```bash
cd services/mcp
AGENT_MCP_SECRET=dev-secret-change-in-prod \
./motis-mcp operator-http
```

Equivalent `make` targets:

```bash
cd services/mcp
make data-http
make execution-http
make operator-http
make test
```

If you prefer `uv` directly, run through the workspace-managed environment
instead of bare `python3`, otherwise search/runtime dependencies may be missing
from the active interpreter.

Then point the agent at the hosted data service:

```bash
RUNTIME_MODE=platform
DATA_MCP_URL=http://localhost:8002
AGENT_MCP_SECRET=dev-secret-change-in-prod
```

## Important Note

This workspace is still in a transition state:

- `motis_data_mcp` is the most functional hosted service today.
- `motis_execution_mcp` has a real paper-trade and risk-guard boundary, but
  live exchange integration is still stubbed.
- `motis_operator_mcp` exposes the control-plane contract, but the runtime
  implementation is still mostly placeholder.

So the main structural issue was not the folder itself. It was the uneven
service maturity and transport consistency across the three packages.
