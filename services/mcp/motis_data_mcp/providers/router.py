"""Provider routing for Motis data tools."""

from __future__ import annotations

import os
from dataclasses import dataclass

from motis_data_mcp.contracts import ReadUrlRequest, ToolEnvelope, WebCrawlRequest, WebExtractRequest, WebSearchRequest
from motis_data_mcp.providers.base import (
    StubSearchProvider,
    StubCrawlProvider,
    StubExtractProvider,
    WebCrawlProvider,
    WebExtractProvider,
    WebSearchProvider,
    single_url_to_extract_request,
)
from motis_data_mcp.providers.ddg import DDGSearchProvider
from motis_data_mcp.providers.http_reader import HTTPReaderProvider
from motis_data_mcp.providers.market import MarketDataRouter
from motis_data_mcp.providers.research import ResearchDataRouter
from motis_data_mcp.providers.search import FederatedSearchProvider


def _env(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().lower()
    return value or default


def _resolve_search_provider() -> WebSearchProvider:
    provider_name = _env("MOTIS_WEB_SEARCH_PROVIDER", "federated")
    if provider_name in {"federated", "motis_search", "multi"}:
        return FederatedSearchProvider()
    if provider_name == "ddg":
        return DDGSearchProvider()
    return StubSearchProvider(
        name=provider_name,
        message=(
            "Motis search routing is configured, but the selected search provider is "
            "not wired yet."
        ),
    )


def _resolve_extract_provider() -> WebExtractProvider:
    provider_name = _env("MOTIS_WEB_EXTRACT_PROVIDER", "motis_reader")
    if provider_name in {"motis_reader", "http", "http_reader"}:
        return HTTPReaderProvider()
    return StubExtractProvider(
        name=provider_name,
        message=(
            "Motis URL reading now has a stable MCP contract, but the configured extract "
            "provider is not wired yet."
        ),
    )


def _resolve_crawl_provider() -> WebCrawlProvider:
    provider_name = _env("MOTIS_WEB_CRAWL_PROVIDER", "motis_crawler")
    return StubCrawlProvider(
        name=provider_name,
        message=(
            "Motis site crawling now has a stable MCP contract, but the configured crawl "
            "provider is not wired yet."
        ),
    )


@dataclass(slots=True)
class NetworkingRouter:
    search_provider: WebSearchProvider
    extract_provider: WebExtractProvider
    crawl_provider: WebCrawlProvider
    market_router: MarketDataRouter
    research_router: ResearchDataRouter

    async def web_search(self, request: WebSearchRequest) -> ToolEnvelope:
        return await self.search_provider.search(request)

    async def web_extract(self, request: WebExtractRequest) -> ToolEnvelope:
        return await self.extract_provider.extract(request, tool_name="web_extract")

    async def read_url(self, request: ReadUrlRequest, *, tool_name: str) -> ToolEnvelope:
        extract_request = single_url_to_extract_request(request)
        return await self.extract_provider.extract(extract_request, tool_name=tool_name)

    async def web_crawl(self, request: WebCrawlRequest) -> ToolEnvelope:
        return await self.crawl_provider.crawl(request)

    def market_resolve_symbol(self, symbol: str, *, exchange: str | None = None) -> ToolEnvelope:
        return self.market_router.resolve_symbol(symbol, exchange=exchange)

    async def market_get_ohlcv(
        self,
        symbol: str,
        *,
        interval: str,
        limit: int = 200,
        exchange: str | None = None,
    ) -> ToolEnvelope:
        return await self.market_router.get_ohlcv(symbol, interval, limit=limit, exchange=exchange)

    async def market_get_ticker(self, symbol: str, *, exchange: str | None = None) -> ToolEnvelope:
        return await self.market_router.get_ticker(symbol, exchange=exchange)

    async def market_get_orderbook(
        self,
        symbol: str,
        *,
        limit: int = 20,
        exchange: str | None = None,
    ) -> ToolEnvelope:
        return await self.market_router.get_orderbook(symbol, limit=limit, exchange=exchange)

    async def market_get_funding_rate(
        self,
        symbol: str,
        *,
        limit: int = 50,
        exchange: str | None = None,
    ) -> ToolEnvelope:
        return await self.market_router.get_funding_rate(symbol, limit=limit, exchange=exchange)

    async def market_get_open_interest(
        self,
        symbol: str,
        *,
        limit: int = 50,
        exchange: str | None = None,
    ) -> ToolEnvelope:
        return await self.market_router.get_open_interest(symbol, limit=limit, exchange=exchange)

    async def macro_get_series(
        self,
        *,
        series: str,
        country: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        frequency: str | None = None,
    ) -> ToolEnvelope:
        return await self.research_router.get_macro_series(
            series=series,
            country=country,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
        )

    async def equity_get_fundamentals(
        self,
        *,
        symbols: list[str],
        fields: list[str] | None = None,
        as_of: str | None = None,
        frequency: str | None = None,
    ) -> ToolEnvelope:
        return await self.research_router.get_equity_fundamentals(
            symbols=symbols,
            fields=fields,
            as_of=as_of,
            frequency=frequency,
        )

    async def equity_get_earnings_calendar(
        self,
        *,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
    ) -> ToolEnvelope:
        return await self.research_router.get_equity_earnings_calendar(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    async def flows_get_connect(
        self,
        *,
        direction: str,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> ToolEnvelope:
        return await self.research_router.get_connect(
            direction=direction,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )

    async def china_get_moneyflow(
        self,
        *,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        granularity: str | None = None,
    ) -> ToolEnvelope:
        return await self.research_router.get_china_moneyflow(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
        )


_ROUTER: NetworkingRouter | None = None


def get_networking_router() -> NetworkingRouter:
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = NetworkingRouter(
            search_provider=_resolve_search_provider(),
            extract_provider=_resolve_extract_provider(),
            crawl_provider=_resolve_crawl_provider(),
            market_router=MarketDataRouter(),
            research_router=ResearchDataRouter(),
        )
    return _ROUTER
