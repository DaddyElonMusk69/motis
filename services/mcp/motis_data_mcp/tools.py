"""
Data MCP tools.

The live surface stays intentionally narrow, but the tools listed in
``ACTIVE_DATA_TOOLS`` are wired end to end through Motis-owned routing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

try:
    from mcp.types import TextContent, Tool
except ModuleNotFoundError:  # pragma: no cover - local smoke-test fallback
    @dataclass(slots=True)
    class TextContent:  # type: ignore[override]
        type: str
        text: str

    @dataclass(slots=True)
    class Tool:  # type: ignore[override]
        name: str
        description: str
        inputSchema: dict

from motis_data_mcp.contracts import (
    CRAWL_MODES,
    READ_FORMATS,
    SEARCH_SORT_ORDERS,
    SEARCH_VERTICALS,
    ReadUrlRequest,
    WebCrawlRequest,
    WebExtractRequest,
    WebSearchRequest,
    build_not_implemented_envelope,
    build_validation_error_envelope,
)
from motis_data_mcp.providers import get_networking_router


def _json_content(payload: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload))]


def _clean_str(value: object, *, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _clean_int(value: object, *, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _clean_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _clean_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        item_str = _clean_str(item)
        if item_str:
            cleaned.append(item_str)
    return cleaned


def _web_search_request(args: dict) -> WebSearchRequest:
    query = _clean_str(args.get("query"))
    if not query:
        raise ValueError("web_search requires a non-empty query")

    vertical = _clean_str(args.get("vertical"), default="general") or "general"
    if vertical not in SEARCH_VERTICALS:
        raise ValueError(f"web_search vertical must be one of: {', '.join(SEARCH_VERTICALS)}")

    sort_by = _clean_str(args.get("sort_by"), default="relevance") or "relevance"
    if sort_by not in SEARCH_SORT_ORDERS:
        raise ValueError(f"web_search sort_by must be one of: {', '.join(SEARCH_SORT_ORDERS)}")

    return WebSearchRequest(
        query=query,
        limit=_clean_int(args.get("limit"), default=5, minimum=1, maximum=10),
        vertical=vertical,
        sort_by=sort_by,
        allowed_domains=_clean_str_list(args.get("allowed_domains")),
        blocked_domains=_clean_str_list(args.get("blocked_domains")),
        max_age_hours=(
            _clean_int(args.get("max_age_hours"), default=24, minimum=1)
            if args.get("max_age_hours") is not None
            else None
        ),
        region=_clean_str(args.get("region")) or None,
        include_content=_clean_bool(args.get("include_content"), default=False),
    )


def _web_extract_request(args: dict) -> WebExtractRequest:
    urls = _clean_str_list(args.get("urls"))
    if not urls:
        raise ValueError("web_extract requires at least one URL")

    output_format = _clean_str(args.get("format"), default="markdown") or "markdown"
    if output_format not in READ_FORMATS:
        raise ValueError(f"web_extract format must be one of: {', '.join(READ_FORMATS)}")

    return WebExtractRequest(
        urls=urls[:5],
        format=output_format,
        prompt=_clean_str(args.get("prompt")) or None,
        max_chars_per_url=(
            _clean_int(args.get("max_chars_per_url"), default=20000, minimum=500)
            if args.get("max_chars_per_url") is not None
            else None
        ),
        timeout_seconds=_clean_int(args.get("timeout_seconds"), default=30, minimum=5, maximum=180),
    )


def _read_url_request(args: dict) -> ReadUrlRequest:
    url = _clean_str(args.get("url"))
    if not url:
        raise ValueError("read_url requires a non-empty url")

    output_format = _clean_str(args.get("format"), default="markdown") or "markdown"
    if output_format not in READ_FORMATS:
        raise ValueError(f"read_url format must be one of: {', '.join(READ_FORMATS)}")

    return ReadUrlRequest(
        url=url,
        format=output_format,
        prompt=_clean_str(args.get("prompt")) or None,
        max_chars=(
            _clean_int(args.get("max_chars"), default=20000, minimum=500)
            if args.get("max_chars") is not None
            else None
        ),
        timeout_seconds=_clean_int(args.get("timeout_seconds"), default=30, minimum=5, maximum=180),
    )


def _web_crawl_request(args: dict) -> WebCrawlRequest:
    root_url = _clean_str(args.get("root_url"))
    if not root_url:
        raise ValueError("web_crawl requires a non-empty root_url")

    mode = _clean_str(args.get("mode"), default="extract") or "extract"
    if mode not in CRAWL_MODES:
        raise ValueError(f"web_crawl mode must be one of: {', '.join(CRAWL_MODES)}")

    return WebCrawlRequest(
        root_url=root_url,
        prompt=_clean_str(args.get("prompt")) or None,
        mode=mode,
        max_pages=_clean_int(args.get("max_pages"), default=5, minimum=1, maximum=20),
        same_domain_only=_clean_bool(args.get("same_domain_only"), default=True),
        allowed_domains=_clean_str_list(args.get("allowed_domains")),
        blocked_domains=_clean_str_list(args.get("blocked_domains")),
    )


def _market_symbol(args: dict, *, tool_name: str) -> str:
    symbol = _clean_str(args.get("symbol"))
    if not symbol:
        raise ValueError(f"{tool_name} requires a non-empty symbol")
    return symbol


def _market_exchange(args: dict) -> str | None:
    exchange = _clean_str(args.get("exchange"))
    return exchange or None


def _market_interval(args: dict, *, tool_name: str) -> str:
    interval = _clean_str(args.get("interval"))
    if not interval:
        raise ValueError(f"{tool_name} requires a non-empty interval")
    return interval


def _market_resolve_request(args: dict) -> dict[str, object]:
    return {
        "symbol": _market_symbol(args, tool_name="market.resolve_symbol"),
        "exchange": _market_exchange(args),
    }


def _market_ohlcv_request(args: dict) -> dict[str, object]:
    return {
        "symbol": _market_symbol(args, tool_name="market.get_ohlcv"),
        "interval": _market_interval(args, tool_name="market.get_ohlcv"),
        "limit": _clean_int(args.get("limit"), default=200, minimum=1, maximum=2000),
        "exchange": _market_exchange(args),
    }


def _market_ticker_request(args: dict) -> dict[str, object]:
    return {
        "symbol": _market_symbol(args, tool_name="market.get_ticker"),
        "exchange": _market_exchange(args),
    }


def _market_orderbook_request(args: dict) -> dict[str, object]:
    return {
        "symbol": _market_symbol(args, tool_name="market.get_orderbook"),
        "limit": _clean_int(args.get("limit"), default=20, minimum=1, maximum=400),
        "exchange": _market_exchange(args),
    }


def _market_funding_rate_request(args: dict) -> dict[str, object]:
    return {
        "symbol": _market_symbol(args, tool_name="market.get_funding_rate"),
        "limit": _clean_int(args.get("limit"), default=50, minimum=1, maximum=100),
        "exchange": _market_exchange(args),
    }


def _market_open_interest_request(args: dict) -> dict[str, object]:
    return {
        "symbol": _market_symbol(args, tool_name="market.get_open_interest"),
        "limit": _clean_int(args.get("limit"), default=50, minimum=1, maximum=100),
        "exchange": _market_exchange(args),
    }


def _macro_series_request(args: dict) -> dict[str, object]:
    series = _clean_str(args.get("series"))
    if not series:
        raise ValueError("macro.get_series requires a non-empty series")
    return {
        "series": series,
        "country": _clean_str(args.get("country")) or None,
        "start_date": _clean_str(args.get("start_date")) or None,
        "end_date": _clean_str(args.get("end_date")) or None,
        "frequency": _clean_str(args.get("frequency")) or None,
    }


def _symbols_request(args: dict, *, tool_name: str) -> list[str]:
    symbols = _clean_str_list(args.get("symbols"))
    if not symbols:
        raise ValueError(f"{tool_name} requires at least one symbol")
    return symbols


def _equity_fundamentals_request(args: dict) -> dict[str, object]:
    return {
        "symbols": _symbols_request(args, tool_name="equity.get_fundamentals"),
        "fields": _clean_str_list(args.get("fields")) or None,
        "as_of": _clean_str(args.get("as_of")) or None,
        "frequency": _clean_str(args.get("frequency")) or None,
    }


def _equity_earnings_calendar_request(args: dict) -> dict[str, object]:
    return {
        "symbols": _symbols_request(args, tool_name="equity.get_earnings_calendar"),
        "start_date": _clean_str(args.get("start_date")) or None,
        "end_date": _clean_str(args.get("end_date")) or None,
        "limit": _clean_int(args.get("limit"), default=50, minimum=1, maximum=200),
    }


def _flows_connect_request(args: dict) -> dict[str, object]:
    direction = _clean_str(args.get("direction"), default="both") or "both"
    if direction not in {"northbound", "southbound", "both"}:
        raise ValueError("flows.get_connect direction must be one of: northbound, southbound, both")
    return {
        "direction": direction,
        "symbols": _clean_str_list(args.get("symbols")),
        "start_date": _clean_str(args.get("start_date")) or None,
        "end_date": _clean_str(args.get("end_date")) or None,
    }


def _china_moneyflow_request(args: dict) -> dict[str, object]:
    return {
        "symbols": _symbols_request(args, tool_name="china.get_moneyflow"),
        "start_date": _clean_str(args.get("start_date")) or None,
        "end_date": _clean_str(args.get("end_date")) or None,
        "granularity": _clean_str(args.get("granularity")) or None,
    }


def _tool(
    *,
    name: str,
    description: str,
    properties: dict[str, dict],
    required: tuple[str, ...] = (),
) -> Tool:
    return Tool(
        name=name,
        description=description,
        inputSchema={
            "type": "object",
            "properties": properties,
            "required": list(required),
        },
    )


ACTIVE_DATA_TOOLS: list[Tool] = [
    Tool(
        name="web_search",
        description=(
            "Search the public web through a Motis-owned networking boundary. "
            "Motis routes queries across multiple search engines behind this contract."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                "vertical": {"type": "string", "enum": list(SEARCH_VERTICALS), "default": "general"},
                "sort_by": {"type": "string", "enum": list(SEARCH_SORT_ORDERS), "default": "relevance"},
                "max_age_hours": {"type": "integer", "minimum": 1},
                "region": {"type": "string"},
                "include_content": {"type": "boolean", "default": False},
                "allowed_domains": {"type": "array", "items": {"type": "string"}},
                "blocked_domains": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="web_extract",
        description=(
            "Fetch and normalize one or more public URLs into markdown, text, HTML, or JSON. "
            "Read-only Motis networking boundary."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 5,
                },
                "format": {"type": "string", "enum": list(READ_FORMATS), "default": "markdown"},
                "prompt": {"type": "string"},
                "max_chars_per_url": {"type": "integer", "minimum": 500},
                "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 180, "default": 30},
            },
            "required": ["urls"],
        },
    ),
    Tool(
        name="read_url",
        description=(
            "Compatibility alias for reading a single public URL through the Motis networking boundary."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "format": {"type": "string", "enum": list(READ_FORMATS), "default": "markdown"},
                "prompt": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 500},
                "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 180, "default": 30},
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="web_fetch",
        description="Compatibility alias for read_url.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "format": {"type": "string", "enum": list(READ_FORMATS), "default": "markdown"},
                "prompt": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 500},
                "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 180, "default": 30},
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="web_crawl",
        description=(
            "Crawl a site through a Motis-owned networking boundary. "
            "Useful for provider-backed multi-page discovery later."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "root_url": {"type": "string"},
                "prompt": {"type": "string"},
                "mode": {"type": "string", "enum": list(CRAWL_MODES), "default": "extract"},
                "max_pages": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                "same_domain_only": {"type": "boolean", "default": True},
                "allowed_domains": {"type": "array", "items": {"type": "string"}},
                "blocked_domains": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["root_url"],
        },
    ),
    Tool(
        name="market.get_ohlcv",
        description="Read-only OHLCV access through Motis-owned market-data adapters.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "interval": {"type": "string"},
                "limit": {"type": "integer"},
                "exchange": {"type": "string"},
            },
            "required": ["symbol", "interval"],
        },
    ),
    Tool(
        name="market.get_ticker",
        description="Read-only ticker access through Motis-owned market-data adapters.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "exchange": {"type": "string"},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="market.get_orderbook",
        description="Read-only order book access through Motis-owned market-data adapters.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "exchange": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="market.resolve_symbol",
        description="Resolve a user-facing symbol into a normalized Motis instrument identity.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "exchange": {"type": "string"},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="market.get_funding_rate",
        description="Read-only perpetual funding-rate access through Motis-owned market-data adapters.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "exchange": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="market.get_open_interest",
        description="Read-only open-interest access through Motis-owned market-data adapters.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "exchange": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
            },
            "required": ["symbol"],
        },
    ),
    _tool(
        name="macro.get_series",
        description="Fetch normalized macroeconomic time series through structured Motis data adapters.",
        properties={
            "series": {"type": "string"},
            "country": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            "frequency": {"type": "string"},
        },
        required=("series",),
    ),
    _tool(
        name="equity.get_fundamentals",
        description="Fetch normalized equity fundamentals, valuation fields, and quality metrics.",
        properties={
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "fields": {"type": "array", "items": {"type": "string"}},
            "as_of": {"type": "string", "description": "YYYY-MM-DD"},
            "frequency": {"type": "string"},
        },
        required=("symbols",),
    ),
    _tool(
        name="equity.get_earnings_calendar",
        description="Fetch upcoming and historical earnings dates and guidance windows.",
        properties={
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        },
        required=("symbols",),
    ),
    _tool(
        name="flows.get_connect",
        description="Fetch Northbound and Southbound connect flow summaries and security-level details.",
        properties={
            "direction": {"type": "string", "enum": ["northbound", "southbound", "both"]},
            "symbols": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    ),
    _tool(
        name="china.get_moneyflow",
        description="Fetch A-share and sector moneyflow data through a structured Motis contract.",
        properties={
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            "granularity": {"type": "string"},
        },
        required=("symbols",),
    ),
]


PLANNED_DATA_TOOLS: list[Tool] = [
    _tool(
        name="market.list_instruments",
        description="List instruments available for a market, exchange, or search query.",
        properties={
            "market": {"type": "string"},
            "exchange": {"type": "string"},
            "query": {"type": "string"},
            "instrument_type": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        },
    ),
    _tool(
        name="market.get_trades",
        description="Fetch recent public trade prints through Motis-owned market-data adapters.",
        properties={
            "symbol": {"type": "string"},
            "exchange": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
            "since": {"type": "string", "description": "ISO-8601 timestamp"},
        },
        required=("symbol",),
    ),
    _tool(
        name="market.get_options_chain",
        description="Fetch option chain snapshots, strikes, implied vols, and greeks where available.",
        properties={
            "symbol": {"type": "string"},
            "exchange": {"type": "string"},
            "expiry": {"type": "string", "description": "YYYY-MM-DD"},
            "as_of": {"type": "string", "description": "ISO-8601 timestamp"},
        },
        required=("symbol",),
    ),
    _tool(
        name="market.get_corporate_actions",
        description="Fetch dividends, splits, rights issues, and other corporate-action events.",
        properties={
            "symbol": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("symbol",),
    ),
    _tool(
        name="macro.get_release_calendar",
        description="Fetch macroeconomic release calendars and expected release windows.",
        properties={
            "countries": {"type": "array", "items": {"type": "string"}},
            "categories": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            "importance": {"type": "string"},
        },
    ),
    _tool(
        name="macro.get_policy_doc",
        description="Fetch central-bank, ministry, or regulator policy documents through a structured Motis contract.",
        properties={
            "institution": {"type": "string"},
            "query": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
        required=("institution",),
    ),
    _tool(
        name="macro.get_curve_snapshot",
        description="Fetch a rates-curve snapshot or time series for key government and policy curves.",
        properties={
            "curve": {"type": "string"},
            "as_of": {"type": "string", "description": "YYYY-MM-DD"},
            "tenors": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("curve",),
    ),
    _tool(
        name="equity.get_filings",
        description="Fetch normalized filing metadata and document links for equities.",
        properties={
            "symbol": {"type": "string"},
            "filing_types": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        required=("symbol",),
    ),
    _tool(
        name="equity.get_estimates",
        description="Fetch analyst estimates, revision direction, and consensus summary fields.",
        properties={
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "metrics": {"type": "array", "items": {"type": "string"}},
            "horizon": {"type": "string"},
            "as_of": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("symbols",),
    ),
    _tool(
        name="equity.get_holders",
        description="Fetch institutional holders, insider activity, and ownership snapshots.",
        properties={
            "symbol": {"type": "string"},
            "holder_type": {"type": "string"},
            "as_of": {"type": "string", "description": "YYYY-MM-DD"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        },
        required=("symbol",),
    ),
    _tool(
        name="flows.get_etf",
        description="Fetch ETF flow series and holdings-change summaries.",
        properties={
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            "metric": {"type": "string"},
        },
        required=("symbols",),
    ),
    _tool(
        name="flows.get_fund_flows",
        description="Fetch broader fund-flow datasets across sectors, styles, or fund universes.",
        properties={
            "universe": {"type": "string"},
            "granularity": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("universe",),
    ),
    _tool(
        name="china.get_margin_financing",
        description="Fetch margin financing and securities-lending data for China markets.",
        properties={
            "symbols": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    ),
    _tool(
        name="china.get_sector_breadth",
        description="Fetch sector breadth, limit-up/down, and rotation indicators for China markets.",
        properties={
            "sectors": {"type": "array", "items": {"type": "string"}},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
            "lookback_days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 20},
        },
    ),
    _tool(
        name="china.get_property_hf",
        description="Fetch high-frequency China property data such as sales, starts, or land-auction metrics.",
        properties={
            "metrics": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "cities": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("metrics",),
    ),
    _tool(
        name="china.get_rates",
        description="Fetch China-specific rates such as LPR, MLF, Shibor, DR007, and government curves.",
        properties={
            "curves": {"type": "array", "items": {"type": "string"}},
            "tenors": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    ),
    _tool(
        name="china.get_lgfv_spreads",
        description="Fetch LGFV and regional-credit spread datasets for China fixed-income research.",
        properties={
            "regions": {"type": "array", "items": {"type": "string"}},
            "ratings": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    ),
    _tool(
        name="crypto.get_onchain_metrics",
        description="Fetch normalized on-chain metrics such as MVRV, SOPR, NVT, active addresses, and hash rate.",
        properties={
            "assets": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "metrics": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "interval": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("assets", "metrics"),
    ),
    _tool(
        name="crypto.get_exchange_flows",
        description="Fetch exchange inflow/outflow and reserve metrics for digital assets.",
        properties={
            "assets": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "exchanges": {"type": "array", "items": {"type": "string"}},
            "flow_type": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("assets",),
    ),
    _tool(
        name="crypto.get_stablecoin_flows",
        description="Fetch stablecoin supply, mint/burn, and chain-level flow metrics.",
        properties={
            "stablecoins": {"type": "array", "items": {"type": "string"}},
            "chains": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    ),
    _tool(
        name="crypto.get_defi_tvl",
        description="Fetch DeFi TVL, protocol revenue, and chain-level liquidity metrics.",
        properties={
            "protocols": {"type": "array", "items": {"type": "string"}},
            "chains": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    ),
    _tool(
        name="crypto.get_token_unlocks",
        description="Fetch token unlock schedules and treasury-related release events.",
        properties={
            "assets": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    ),
    _tool(
        name="crypto.get_liquidations",
        description="Fetch liquidation and squeeze metrics across derivatives venues.",
        properties={
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "exchanges": {"type": "array", "items": {"type": "string"}},
            "interval": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("symbols",),
    ),
    _tool(
        name="credit.get_spreads",
        description="Fetch credit spread datasets by rating, sector, region, or issuer universe.",
        properties={
            "universe": {"type": "string"},
            "ratings": {"type": "array", "items": {"type": "string"}},
            "sectors": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("universe",),
    ),
    _tool(
        name="credit.get_curve",
        description="Fetch credit and government yield-curve time series for fixed-income analysis.",
        properties={
            "curve": {"type": "string"},
            "tenors": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("curve",),
    ),
    _tool(
        name="credit.get_issuer_metrics",
        description="Fetch issuer-level leverage, coverage, liquidity, and default-risk metrics.",
        properties={
            "issuers": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "fields": {"type": "array", "items": {"type": "string"}},
            "as_of": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("issuers",),
    ),
    _tool(
        name="credit.get_rating_events",
        description="Fetch rating changes, outlook changes, and related credit events.",
        properties={
            "issuers": {"type": "array", "items": {"type": "string"}},
            "event_types": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    ),
    _tool(
        name="commodity.get_inventory",
        description="Fetch commodity inventory levels across exchanges, warehouses, or logistics hubs.",
        properties={
            "commodities": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "locations": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("commodities",),
    ),
    _tool(
        name="commodity.get_supply_demand",
        description="Fetch supply, demand, production, and balance-sheet metrics for commodities.",
        properties={
            "commodities": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "granularity": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("commodities",),
    ),
    _tool(
        name="commodity.get_shipping_rates",
        description="Fetch shipping and freight rate indices such as SCFI, BDI, or route-level benchmarks.",
        properties={
            "routes": {"type": "array", "items": {"type": "string"}},
            "indices": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
    ),
    _tool(
        name="commodity.get_energy_balance",
        description="Fetch energy-specific balance data such as crude, gas, LNG, and power-market inputs.",
        properties={
            "commodities": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "regions": {"type": "array", "items": {"type": "string"}},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("commodities",),
    ),
    _tool(
        name="dataset.get_price_panel",
        description="Export normalized panel data for prices, volume, and market fields across a symbol universe.",
        properties={
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "fields": {"type": "array", "items": {"type": "string"}},
            "interval": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("symbols", "start_date", "end_date"),
    ),
    _tool(
        name="dataset.get_return_panel",
        description="Export normalized return panels for quant research and cross-sectional analysis.",
        properties={
            "symbols": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "interval": {"type": "string"},
            "return_type": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("symbols", "start_date", "end_date"),
    ),
    _tool(
        name="dataset.get_factor_panel",
        description="Export normalized factor panels for multi-factor research and ranking workflows.",
        properties={
            "universe": {"type": "string"},
            "factors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "frequency": {"type": "string"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("universe", "factors", "start_date", "end_date"),
    ),
    _tool(
        name="dataset.get_event_panel",
        description="Export event panels for earnings, filings, policy, corporate, or macro-event studies.",
        properties={
            "universe": {"type": "string"},
            "event_types": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        required=("universe", "event_types", "start_date", "end_date"),
    ),
]


DATA_PROVIDER_ROUTING_PLAN: dict[str, object] = {
    "structured_market_routing": {
        "a_share": ["tushare", "yfinance", "akshare"],
        "us_equity": ["yfinance", "akshare"],
        "hk_equity": ["yfinance", "akshare"],
        "crypto": ["okx", "ccxt"],
        "futures": ["tushare", "akshare"],
        "fund": ["tushare", "akshare"],
        "macro": ["akshare", "tushare"],
        "forex": ["akshare", "yfinance"],
    },
    "document_and_web_routing": {
        "discovery": ["web_search"],
        "single_url": ["read_url", "web_fetch"],
        "multi_url": ["web_extract"],
        "multi_page": ["web_crawl"],
    },
    "principles": [
        "Structured providers are the default for numeric market, macro, flow, and panel data.",
        "Web tools are for documents, policy releases, filings text, and narrative research.",
        "Free-first adapters ship before paid or premium data providers.",
    ],
}


# Keep the live MCP surface intentionally narrow.
# `PLANNED_DATA_TOOLS` is the next contract inventory we will graduate into
# `DATA_TOOLS` domain by domain as adapters become real.
DATA_TOOLS = ACTIVE_DATA_TOOLS


async def dispatch_data(name: str, args: dict) -> list[TextContent]:
    known_tools = {tool.name for tool in DATA_TOOLS}
    if name not in known_tools:
        raise ValueError(f"Unknown data tool: {name}")

    args = args or {}

    try:
        router = get_networking_router()

        if name == "web_search":
            request = _web_search_request(args)
            return _json_content((await router.web_search(request)).to_dict())

        if name == "web_extract":
            request = _web_extract_request(args)
            return _json_content((await router.web_extract(request)).to_dict())

        if name in {"read_url", "web_fetch"}:
            request = _read_url_request(args)
            return _json_content((await router.read_url(request, tool_name=name)).to_dict())

        if name == "web_crawl":
            request = _web_crawl_request(args)
            return _json_content((await router.web_crawl(request)).to_dict())

        if name == "market.resolve_symbol":
            request = _market_resolve_request(args)
            return _json_content(router.market_resolve_symbol(**request).to_dict())

        if name == "market.get_ohlcv":
            request = _market_ohlcv_request(args)
            return _json_content((await router.market_get_ohlcv(**request)).to_dict())

        if name == "market.get_ticker":
            request = _market_ticker_request(args)
            return _json_content((await router.market_get_ticker(**request)).to_dict())

        if name == "market.get_orderbook":
            request = _market_orderbook_request(args)
            return _json_content((await router.market_get_orderbook(**request)).to_dict())

        if name == "market.get_funding_rate":
            request = _market_funding_rate_request(args)
            return _json_content((await router.market_get_funding_rate(**request)).to_dict())

        if name == "market.get_open_interest":
            request = _market_open_interest_request(args)
            return _json_content((await router.market_get_open_interest(**request)).to_dict())

        if name == "macro.get_series":
            request = _macro_series_request(args)
            return _json_content((await router.macro_get_series(**request)).to_dict())

        if name == "equity.get_fundamentals":
            request = _equity_fundamentals_request(args)
            return _json_content((await router.equity_get_fundamentals(**request)).to_dict())

        if name == "equity.get_earnings_calendar":
            request = _equity_earnings_calendar_request(args)
            return _json_content((await router.equity_get_earnings_calendar(**request)).to_dict())

        if name == "flows.get_connect":
            request = _flows_connect_request(args)
            return _json_content((await router.flows_get_connect(**request)).to_dict())

        if name == "china.get_moneyflow":
            request = _china_moneyflow_request(args)
            return _json_content((await router.china_get_moneyflow(**request)).to_dict())

    except ValueError as exc:
        return _json_content(
            build_validation_error_envelope(tool=name, request=dict(args), message=str(exc)).to_dict()
        )

    return _json_content(
        build_not_implemented_envelope(
            tool=name,
            provider="motis_contract",
            request=dict(args),
            message="This Motis data tool contract exists, but the provider wiring is not implemented yet.",
        ).to_dict()
    )
