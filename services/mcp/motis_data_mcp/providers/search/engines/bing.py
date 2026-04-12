"""Bing engine adapter for Motis federated search."""

from __future__ import annotations

import math
from urllib.parse import urlparse, urlunparse

from lxml import html

from motis_data_mcp.contracts import WebSearchRequest, WebSearchResult
from motis_data_mcp.providers.safety import ensure_safe_result_url
from motis_data_mcp.providers.search.http import request_text

BING_SEARCH_URL = "https://www.bing.com/search"
BING_PAGE_SIZE = 10
_BLOCK_MARKERS = (
    "captcha",
    "verify you are human",
    "access denied",
    "too many requests",
    "blocked",
    "rate limit",
)


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _sanitize_url(raw_url: str) -> str:
    cleaned = raw_url.strip()
    if not cleaned:
        return ""

    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    elif cleaned.startswith("/"):
        if cleaned.startswith("/search") or cleaned.startswith("/ck/a") or cleaned.startswith("/newtabredir"):
            return ""
        cleaned = f"https://www.bing.com{cleaned}"

    if not cleaned.startswith(("http://", "https://")):
        return ""

    parsed = urlparse(cleaned)
    hostname = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if hostname.endswith("bing.com") and path.startswith(("/search", "/ck/a", "/newtabredir")):
        return ""

    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def _extract_source(element: html.HtmlElement, url: str) -> str | None:
    source_candidates = element.xpath(
        './/*[contains(@class, "b_tpcn")]//text()'
        ' | .//*[contains(@class, "b_attribution")]//cite//text()'
        ' | .//cite[1]//text()'
    )
    source = _normalize_text(" ".join(str(value) for value in source_candidates))
    if source:
        return source
    return urlparse(url).hostname or None


def _extract_description(element: html.HtmlElement, title: str) -> str:
    description_candidates = element.xpath(
        './/*[contains(@class, "b_caption")]//p[1]//text()'
        ' | .//*[contains(@class, "b_caption")][1]//text()'
        ' | .//*[contains(@class, "b_snippet")][1]//text()'
        ' | .//*[contains(@class, "b_lineclamp")][1]//text()'
    )
    description = _normalize_text(" ".join(str(value) for value in description_candidates))
    if description:
        return description[:400]

    fallback = _normalize_text(" ".join(element.xpath(".//text()"))).replace(title, "", 1).strip()
    return fallback[:400]


def _parse_results(page_html: str, *, limit: int) -> list[WebSearchResult]:
    document = html.fromstring(page_html)
    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    selectors = (
        '//*[@id="b_results"]/li[contains(@class, "b_algo")]',
        '//*[@id="b_results"]/li[contains(@class, "b_ans")]',
        '//*[@id="b_topw"]/li[contains(@class, "b_algo")]',
        '//*[contains(@class, "b_algo")]',
        '//*[contains(@class, "b_ans")]',
    )

    for selector in selectors:
        for node in document.xpath(selector):
            if len(results) >= limit:
                return results

            class_name = str(node.get("class") or "")
            if "b_ad" in class_name or "b_pag" in class_name or "b_msg" in class_name:
                continue

            link_nodes = node.xpath(
                './/h2//a[@href]'
                ' | .//*[contains(@class, "b_title")]//a[@href]'
                ' | .//a[@target="_blank"][@href]'
                ' | .//a[@href]'
            )
            if not link_nodes:
                continue

            url = _sanitize_url(str(link_nodes[0].get("href") or ""))
            if not url or url in seen_urls:
                continue

            try:
                ensure_safe_result_url(url)
            except ValueError:
                continue

            title = _normalize_text(" ".join(link_nodes[0].xpath(".//text()"))) or _normalize_text(
                " ".join(node.xpath(".//h2[1]//text() | .//h3[1]//text()"))
            )
            if not title:
                title = f"Result from {urlparse(url).hostname or 'web'}"

            seen_urls.add(url)
            results.append(
                WebSearchResult(
                    title=title[:200],
                    url=url,
                    snippet=_extract_description(node, title),
                    source=_extract_source(node, url),
                    engine="bing",
                )
            )

    if results:
        return results

    for link in document.xpath('//*[@id="b_results"]//a[@href] | //*[@id="b_topw"]//a[@href]'):
        if len(results) >= limit:
            break

        url = _sanitize_url(str(link.get("href") or ""))
        if not url or url in seen_urls:
            continue

        try:
            ensure_safe_result_url(url)
        except ValueError:
            continue

        container = link.getparent()
        title = _normalize_text(" ".join(link.xpath(".//text()"))) or f"Result from {urlparse(url).hostname or 'web'}"
        snippet = ""
        if container is not None:
            snippet = _normalize_text(" ".join(container.xpath(".//text()"))).replace(title, "", 1).strip()[:400]

        seen_urls.add(url)
        results.append(
            WebSearchResult(
                title=title[:200],
                url=url,
                snippet=snippet,
                source=urlparse(url).hostname or None,
                engine="bing",
            )
        )

    return results


def _raise_if_blocked(page_html: str, parsed_results: list[WebSearchResult]) -> None:
    lowered = page_html.lower()
    title = ""
    try:
        title_doc = html.fromstring(page_html)
        title = _normalize_text(" ".join(title_doc.xpath("//title[1]//text()"))).lower()
    except Exception:
        title = ""

    if parsed_results:
        return

    if any(marker in lowered or marker in title for marker in _BLOCK_MARKERS):
        raise RuntimeError("Bing returned a blocked or verification page.")


async def _search_page(query: str, *, page: int) -> list[WebSearchResult]:
    page_html = await request_text(
        BING_SEARCH_URL,
        params={
            "q": query,
            "first": str(1 + (page - 1) * BING_PAGE_SIZE),
        },
    )
    results = _parse_results(page_html, limit=BING_PAGE_SIZE)
    _raise_if_blocked(page_html, results)
    return results


async def search_bing(request: WebSearchRequest, query: str, limit: int) -> list[WebSearchResult]:
    del request
    if limit <= 0:
        return []

    max_page = max(1, math.ceil(limit / BING_PAGE_SIZE))
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
