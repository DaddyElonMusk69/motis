from __future__ import annotations

import asyncio

from motis_data_mcp.contracts import WebSearchRequest, WebSearchResult
from motis_data_mcp.providers.router import _resolve_search_provider
from motis_data_mcp.providers.search.federated import FederatedSearchProvider


def test_federated_provider_merges_results_and_reports_partial_failures():
    async def ddg_engine(request: WebSearchRequest, query: str, limit: int) -> list[WebSearchResult]:
        assert request.query == "fed dot plot"
        assert query == "fed dot plot site:federalreserve.gov -site:example.com"
        assert limit == 2
        return [
            WebSearchResult(
                title="FOMC statement",
                url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm?utm_source=ddg",
                snippet="Latest statement and policy decision.",
                source="federalreserve.gov",
            ),
            WebSearchResult(
                title="SEP release",
                url="https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260128.htm",
                snippet="Summary of Economic Projections.",
                source="federalreserve.gov",
            ),
        ]

    async def startpage_engine(request: WebSearchRequest, query: str, limit: int) -> list[WebSearchResult]:
        assert request.query == "fed dot plot"
        assert query == "fed dot plot site:federalreserve.gov -site:example.com"
        assert limit == 2
        return [
            WebSearchResult(
                title="Federal Reserve FOMC statement",
                url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm",
                snippet="Federal Reserve policy statement with full release details.",
                source="www.federalreserve.gov",
            ),
            WebSearchResult(
                title="Meeting minutes",
                url="https://www.federalreserve.gov/monetarypolicy/fomcminutes20260128.htm",
                snippet="Minutes from the January meeting.",
                source="federalreserve.gov",
            ),
        ]

    async def bing_engine(request: WebSearchRequest, query: str, limit: int) -> list[WebSearchResult]:
        assert request.query == "fed dot plot"
        assert query == "fed dot plot site:federalreserve.gov -site:example.com"
        assert limit == 1
        raise RuntimeError("503 Service Unavailable")

    provider = FederatedSearchProvider(
        engines=("ddg", "startpage", "bing"),
        engine_registry={
            "ddg": ddg_engine,
            "startpage": startpage_engine,
            "bing": bing_engine,
        },
    )

    result = asyncio.run(
        provider.search(
            WebSearchRequest(
                query="fed dot plot",
                limit=5,
                allowed_domains=["federalreserve.gov"],
                blocked_domains=["example.com"],
            )
        )
    )

    assert result.status == "ok"
    assert result.provider == "motis_search"
    assert result.data["engines"] == ["ddg", "startpage", "bing"]
    assert result.data["total_results"] == 3
    assert result.data["partial_failures"] == [
        {
            "engine": "bing",
            "code": "engine_error",
            "message": "503 Service Unavailable",
        }
    ]
    assert result.data["results"] == [
        {
            "title": "Federal Reserve FOMC statement",
            "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm",
            "snippet": "Federal Reserve policy statement with full release details.",
            "source": "federalreserve.gov",
            "published_at": None,
            "score": 1.95,
            "engine": "ddg",
        },
        {
            "title": "SEP release",
            "url": "https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260128.htm",
            "snippet": "Summary of Economic Projections.",
            "source": "federalreserve.gov",
            "published_at": None,
            "score": 0.5,
            "engine": "ddg",
        },
        {
            "title": "Meeting minutes",
            "url": "https://www.federalreserve.gov/monetarypolicy/fomcminutes20260128.htm",
            "snippet": "Minutes from the January meeting.",
            "source": "federalreserve.gov",
            "published_at": None,
            "score": 0.475,
            "engine": "startpage",
        },
    ]
    assert any("Some search engines failed" in warning for warning in result.warnings)


def test_federated_provider_returns_error_when_all_engines_fail():
    async def missing_engine(request: WebSearchRequest, query: str, limit: int) -> list[WebSearchResult]:
        del request, query, limit
        raise ImportError("missing ddgs")

    provider = FederatedSearchProvider(
        engines=("ddg",),
        engine_registry={"ddg": missing_engine},
    )

    result = asyncio.run(provider.search(WebSearchRequest(query="btc funding", limit=3)))

    assert result.status == "error"
    assert result.provider == "motis_search"
    assert result.error == {
        "code": "dependency_missing",
        "message": "All configured search engines failed to return results.",
    }
    assert result.data["engines"] == ["ddg"]
    assert result.data["partial_failures"] == [
        {
            "engine": "ddg",
            "code": "dependency_missing",
            "message": "missing ddgs",
        }
    ]


def test_router_defaults_to_federated_search_provider(monkeypatch):
    monkeypatch.delenv("MOTIS_WEB_SEARCH_PROVIDER", raising=False)

    provider = _resolve_search_provider()

    assert provider.__class__.__name__ == "FederatedSearchProvider"
