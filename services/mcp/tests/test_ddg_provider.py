from __future__ import annotations

import asyncio

from motis_data_mcp.contracts import WebSearchRequest
from motis_data_mcp.providers.ddg import DDGSearchProvider


class _FakeDDGS:
    def __init__(self, results):
        self._results = results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def text(self, query: str, max_results: int):
        assert query == "fed dot plot site:federalreserve.gov -site:example.com"
        assert max_results == 2
        return self._results


def test_ddg_provider_uses_ddgs_package_and_preserves_contract(monkeypatch):
    def fake_loader():
        return lambda: _FakeDDGS(
            [
                {
                    "title": "FOMC statement",
                    "href": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm",
                    "body": "Latest statement and policy decision.",
                    "source": "federalreserve.gov",
                },
                {
                    "title": "Blocked result",
                    "href": "file:///etc/passwd",
                    "body": "Should be filtered out.",
                },
            ]
        )

    monkeypatch.setattr("motis_data_mcp.providers.search.engines.ddg._load_ddgs_cls", fake_loader)

    provider = DDGSearchProvider()
    result = asyncio.run(
        provider.search(
            WebSearchRequest(
                query="fed dot plot",
                limit=2,
                allowed_domains=["federalreserve.gov"],
                blocked_domains=["example.com"],
                vertical="general",
                sort_by="relevance",
            )
        )
    )

    assert result.status == "ok"
    assert result.provider == "ddg_search"
    assert result.data["query"] == "fed dot plot"
    assert result.data["total_results"] == 1
    assert result.data["engines"] == ["ddg"]
    assert result.data["partial_failures"] == []
    assert result.data["results"] == [
        {
            "title": "FOMC statement",
            "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm",
            "snippet": "Latest statement and policy decision.",
            "source": "federalreserve.gov",
            "published_at": None,
            "score": 1.0,
            "engine": "ddg",
        }
    ]


def test_ddg_provider_returns_structured_error_when_dependency_missing(monkeypatch):
    def fake_loader():
        raise ImportError("missing ddgs")

    monkeypatch.setattr("motis_data_mcp.providers.search.engines.ddg._load_ddgs_cls", fake_loader)

    provider = DDGSearchProvider()
    result = asyncio.run(provider.search(WebSearchRequest(query="btc funding", limit=3)))

    assert result.status == "error"
    assert result.error == {
        "code": "dependency_missing",
        "message": "DuckDuckGo search package not installed. Install `ddgs` for web_search.",
    }
    assert result.data["results"] == []
    assert result.data["engines"] == ["ddg"]
