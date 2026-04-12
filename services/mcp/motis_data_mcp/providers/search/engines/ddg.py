"""DuckDuckGo engine adapter for Motis federated search."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from motis_data_mcp.contracts import WebSearchRequest, WebSearchResult
from motis_data_mcp.providers.safety import ensure_safe_result_url


def _load_ddgs_cls():
    try:
        from ddgs import DDGS

        return DDGS
    except ImportError:
        from duckduckgo_search import DDGS

        return DDGS


def _search_sync(query: str, *, limit: int) -> list[dict[str, Any]]:
    ddgs_cls = _load_ddgs_cls()
    with ddgs_cls() as ddgs:
        raw_results = ddgs.text(query, max_results=limit)
        if isinstance(raw_results, list):
            return raw_results
        if isinstance(raw_results, Iterable):
            return list(raw_results)
        return list(raw_results or [])


def _extract_results(raw_results: list[dict[str, Any]], *, limit: int) -> list[WebSearchResult]:
    results: list[WebSearchResult] = []
    for item in raw_results:
        href = str(item.get("href") or item.get("url") or "").strip()
        title = str(item.get("title") or item.get("heading") or "").strip()
        if not title or not href:
            continue

        try:
            ensure_safe_result_url(href)
        except ValueError:
            continue

        snippet = str(item.get("body") or item.get("snippet") or "").strip()
        source = str(item.get("source") or "").strip() or None
        published_at = str(item.get("date") or item.get("published") or item.get("published_at") or "").strip() or None
        results.append(
            WebSearchResult(
                title=title,
                url=href,
                snippet=snippet,
                source=source,
                published_at=published_at,
                engine="ddg",
            )
        )
        if len(results) >= limit:
            break
    return results


async def search_ddg(request: WebSearchRequest, query: str, limit: int) -> list[WebSearchResult]:
    del request
    if limit <= 0:
        return []

    raw_results = await asyncio.to_thread(_search_sync, query, limit=limit)
    return _extract_results(raw_results, limit=limit)
