"""
Motis Web Tools
================
Adapted from NousResearch/hermes-agent tools/web_tools.py (MIT License)

Phase 0: Brave Search API + httpx-based HTML→text extraction.
Phase 1: Add Tavily fallback, newspaper3k parsing, PDF extraction.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from motis_agent.context import UserContext

from motis_agent.settings import settings

logger = logging.getLogger(__name__)

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_BRAVE_HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
}


async def motis_web_search(query: str, ctx: "UserContext") -> dict:
    """
    Full-text web search via Brave Search API.
    Falls back to Tavily if Brave key is not configured.

    Adapted from Hermes web_tools.py:web_search().
    Key difference: API key from settings (not ~/.hermes/config), returns dict not str.
    """
    if not query.strip():
        return {"error": "Empty query"}

    api_key = settings.brave_api_key
    if not api_key:
        return await _tavily_search(query)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _BRAVE_SEARCH_URL,
                params={"q": query, "count": 10, "text_decorations": False},
                headers={**_BRAVE_HEADERS, "X-Subscription-Token": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            })

        return {"query": query, "results": results}

    except Exception as exc:
        logger.warning("Brave search failed: %s — trying Tavily", exc)
        return await _tavily_search(query)


async def _tavily_search(query: str) -> dict:
    """Tavily fallback search."""
    api_key = settings.tavily_api_key
    if not api_key:
        return {
            "error": (
                "No search API key configured. "
                "Set BRAVE_API_KEY or TAVILY_API_KEY in .env"
            )
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": 10},
            )
            resp.raise_for_status()
            data = resp.json()

        results = [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
            for r in data.get("results", [])
        ]
        return {"query": query, "results": results}

    except Exception as exc:
        logger.error("Tavily search also failed: %s", exc)
        return {"error": str(exc), "results": []}


async def motis_web_fetch(url: str, ctx: "UserContext") -> dict:
    """
    Fetch a URL and return cleaned text content.
    Adapted from Hermes web_tools.py:web_extract().
    Phase 0: simple httpx + basic HTML stripping.
    Phase 1: add newspaper3k, PDF extraction, readability.
    """
    if not url.strip():
        return {"error": "Empty URL"}

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MotisFetcher/1.0)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")

            if "text/html" in content_type or "text/plain" in content_type:
                text = _strip_html(resp.text)
            else:
                text = f"[Binary content: {content_type}]"

        return {
            "url": url,
            "content": text[:20_000],  # Truncate to avoid context overflow
            "truncated": len(resp.text) > 20_000,
        }

    except httpx.HTTPStatusError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {url}"}
    except Exception as exc:
        logger.warning("web_fetch failed for %s: %s", url, exc)
        return {"error": str(exc)}


def _strip_html(html: str) -> str:
    """Basic HTML→text. Phase 1 will use newspaper3k/readability."""
    import re
    # Remove script/style blocks
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
