"""Startpage engine adapter for Motis federated search."""

from __future__ import annotations

import asyncio
import math
import re
from urllib.parse import urlparse

from lxml import html

from motis_data_mcp.contracts import WebSearchRequest, WebSearchResult
from motis_data_mcp.providers.safety import ensure_safe_result_url
from motis_data_mcp.providers.search.http import request_text

STARTPAGE_BASE_URL = "https://www.startpage.com"
STARTPAGE_SEARCH_URL = f"{STARTPAGE_BASE_URL}/sp/search"
STARTPAGE_SC_TTL_SECONDS = 30 * 60
STARTPAGE_PAGE_SIZE = 10

_SEARCH_TOKEN: str | None = None
_SEARCH_TOKEN_AT = 0.0
_SEARCH_TOKEN_LOCK = asyncio.Lock()

_CAPTCHA_MARKERS = (
    "/sp/captcha",
    "verify you are human",
    "human verification",
    "security check",
)


def _detect_blocked_page(page_html: str) -> bool:
    lowered = page_html.lower()
    if any(marker in lowered for marker in _CAPTCHA_MARKERS):
        return True
    return False


def _extract_search_token(page_html: str) -> str | None:
    document = html.fromstring(page_html)
    tokens = document.xpath('//form[@action="/sp/search"]//input[@name="sc"]/@value')
    if tokens:
        return str(tokens[0]).strip() or None
    return None


def _extract_interstitial_payload(page_html: str) -> dict[str, str] | None:
    match = re.search(r"var data = (\{[\s\S]*?\});", page_html)
    if not match:
        return None

    payload_text = match.group(1)
    try:
        import json

        raw_payload = json.loads(payload_text)
    except Exception:
        return None

    payload: dict[str, str] = {}
    for key, value in raw_payload.items():
        if isinstance(value, str):
            payload[key] = value
    return payload or None


async def _get_search_token() -> str:
    global _SEARCH_TOKEN, _SEARCH_TOKEN_AT

    now = asyncio.get_running_loop().time()
    if _SEARCH_TOKEN and now - _SEARCH_TOKEN_AT < STARTPAGE_SC_TTL_SECONDS:
        return _SEARCH_TOKEN

    async with _SEARCH_TOKEN_LOCK:
        now = asyncio.get_running_loop().time()
        if _SEARCH_TOKEN and now - _SEARCH_TOKEN_AT < STARTPAGE_SC_TTL_SECONDS:
            return _SEARCH_TOKEN

        page_html = await request_text(f"{STARTPAGE_BASE_URL}/")
        if _detect_blocked_page(page_html):
            raise RuntimeError("Startpage returned a verification page while requesting the search token.")

        token = _extract_search_token(page_html)
        if not token:
            raise RuntimeError("Failed to extract Startpage search token.")

        _SEARCH_TOKEN = token
        _SEARCH_TOKEN_AT = now
        return token


def _clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _extract_result_nodes(document: html.HtmlElement) -> list[html.HtmlElement]:
    nodes = document.xpath(
        '//a[@href and contains(@class, "result-link")]'
        ' | //a[@href and contains(@class, "w-gl__result-title")]'
    )
    return [node for node in nodes if isinstance(node, html.HtmlElement)]


def _extract_results(page_html: str, *, limit: int) -> list[WebSearchResult]:
    if _detect_blocked_page(page_html):
        raise RuntimeError("Startpage returned a verification or anti-bot page.")

    document = html.fromstring(page_html)
    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()

    for link in _extract_result_nodes(document):
        url = str(link.get("href") or "").strip()
        if not url or url in seen_urls:
            continue

        try:
            ensure_safe_result_url(url)
        except ValueError:
            continue

        title = _clean_text(" ".join(link.xpath(".//text()")))
        container = link.getparent()
        snippet = ""
        if container is not None:
            snippet_candidates = container.xpath(
                './/p[contains(@class, "description")][1]//text()'
                ' | .//*[contains(@class, "w-gl__description")][1]//text()'
            )
            snippet = _clean_text(" ".join(str(value) for value in snippet_candidates))

        if not title:
            continue

        seen_urls.add(url)
        source = urlparse(url).hostname or None
        results.append(
            WebSearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source=source,
                engine="startpage",
            )
        )
        if len(results) >= limit:
            break
    return results


async def _search_page(query: str, *, page: int) -> list[WebSearchResult]:
    token = await _get_search_token()
    form_data: dict[str, str] = {
        "query": query,
        "cat": "web",
        "t": "device",
        "sc": token,
        "abp": "1",
        "abd": "1",
        "abe": "1",
    }
    if page > 1:
        form_data["page"] = str(page)
        form_data["segment"] = "startpage.udog"

    page_html = await request_text(
        STARTPAGE_SEARCH_URL,
        method="POST",
        data=form_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": STARTPAGE_BASE_URL,
            "Referer": f"{STARTPAGE_BASE_URL}/",
        },
    )

    interstitial_payload = _extract_interstitial_payload(page_html)
    if interstitial_payload:
        page_html = await request_text(
            STARTPAGE_SEARCH_URL,
            method="POST",
            data=interstitial_payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": STARTPAGE_BASE_URL,
                "Referer": STARTPAGE_SEARCH_URL,
            },
        )

    return _extract_results(page_html, limit=STARTPAGE_PAGE_SIZE)


async def search_startpage(request: WebSearchRequest, query: str, limit: int) -> list[WebSearchResult]:
    del request
    if limit <= 0:
        return []

    max_page = max(1, math.ceil(limit / STARTPAGE_PAGE_SIZE))
    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()

    for page in range(1, max_page + 1):
        page_results = await _search_page(query, page=page)
        for item in page_results:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            results.append(item)
            if len(results) >= limit:
                return results
        if not page_results:
            break

    return results[:limit]
