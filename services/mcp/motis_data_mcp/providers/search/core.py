"""Core helpers for Motis federated web search."""

from __future__ import annotations

from typing import Awaitable, Callable, Iterable, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from motis_data_mcp.contracts import WebSearchRequest, WebSearchResult
from motis_data_mcp.providers.safety import ensure_safe_result_url

SUPPORTED_SEARCH_ENGINES = ("ddg", "startpage", "bing")

ENGINE_ALIASES = {
    "ddg": "ddg",
    "duckduckgo": "ddg",
    "duck_duck_go": "ddg",
    "startpage": "startpage",
    "bing": "bing",
}

ENGINE_WEIGHTS = {
    "ddg": 1.0,
    "startpage": 0.95,
    "bing": 0.9,
}

TRACKING_QUERY_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "source",
        "spm",
        "utm_campaign",
        "utm_content",
        "utm_medium",
        "utm_source",
        "utm_term",
    }
)

SearchEngineExecutor = Callable[[WebSearchRequest, str, int], Awaitable[list[WebSearchResult]]]


def normalize_engine_name(engine: str) -> str:
    cleaned = engine.strip().lower()
    compact = cleaned.replace("-", "").replace("_", "").replace(".", "").replace(" ", "")
    return ENGINE_ALIASES.get(compact, cleaned)


def resolve_engine_names(engines: Sequence[str] | str | None) -> list[str]:
    if engines is None:
        raw_engines: Iterable[str] = SUPPORTED_SEARCH_ENGINES
    elif isinstance(engines, str):
        raw_engines = engines.split(",")
    else:
        raw_engines = engines

    resolved: list[str] = []
    seen: set[str] = set()
    for engine in raw_engines:
        normalized = normalize_engine_name(str(engine))
        if not normalized or normalized in seen:
            continue
        resolved.append(normalized)
        seen.add(normalized)
    return resolved


def distribute_limit(total_limit: int, engine_count: int) -> list[int]:
    if engine_count <= 0:
        return []

    base = total_limit // engine_count
    remainder = total_limit % engine_count
    return [base + (1 if index < remainder else 0) for index in range(engine_count)]


def decorate_search_request(request: WebSearchRequest) -> tuple[str, list[str]]:
    query = request.query.strip()
    warnings: list[str] = []

    for domain in request.allowed_domains:
        query += f" site:{domain}"
    for domain in request.blocked_domains:
        query += f" -site:{domain}"

    if request.vertical != "general":
        warnings.append(
            f"Search engines are running best-effort web search for vertical='{request.vertical}'."
        )
    if request.sort_by == "recent":
        warnings.append(
            "Search engines do not guarantee strict recency ordering; results are still best-effort."
        )
    if request.max_age_hours is not None:
        warnings.append(
            "Search engines do not guarantee strict max_age_hours filtering; use recency as best-effort."
        )
    if request.region:
        warnings.append(
            f"Region biasing for region='{request.region}' is best-effort across search engines."
        )
    if request.include_content:
        warnings.append(
            "web_search returns snippets only; use read_url or web_extract for full page content."
        )

    return query, warnings


def assign_engine_scores(engine: str, results: Sequence[WebSearchResult]) -> list[WebSearchResult]:
    weight = ENGINE_WEIGHTS.get(engine, 0.8)
    scored: list[WebSearchResult] = []
    for index, result in enumerate(results):
        score = result.score if result.score is not None else weight / (index + 1)
        scored.append(
            WebSearchResult(
                title=result.title,
                url=result.url,
                snippet=result.snippet,
                source=result.source,
                published_at=result.published_at,
                score=score,
                engine=result.engine or engine,
            )
        )
    return scored


def canonicalize_result_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return url

    port = parsed.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        if key.lower() in TRACKING_QUERY_PARAMS:
            continue
        query_pairs.append((key, value))

    path = parsed.path or "/"
    query = urlencode(query_pairs, doseq=True)
    return urlunparse((scheme, netloc, path.rstrip("/") or "/", "", query, ""))


def _pick_better_text(current: str, candidate: str) -> str:
    current_clean = current.strip()
    candidate_clean = candidate.strip()
    if not current_clean:
        return candidate_clean
    if len(candidate_clean) > len(current_clean):
        return candidate_clean
    return current_clean


def merge_search_results(results: Sequence[WebSearchResult], *, limit: int) -> list[WebSearchResult]:
    merged: dict[str, WebSearchResult] = {}
    first_seen: dict[str, int] = {}

    for index, result in enumerate(results):
        try:
            ensure_safe_result_url(result.url)
        except ValueError:
            continue

        key = canonicalize_result_url(result.url)
        if key not in merged:
            merged[key] = WebSearchResult(
                title=result.title.strip(),
                url=key,
                snippet=result.snippet.strip(),
                source=(result.source or "").strip() or None,
                published_at=(result.published_at or "").strip() or None,
                score=float(result.score or 0.0),
                engine=result.engine,
            )
            first_seen[key] = index
            continue

        existing = merged[key]
        existing.title = _pick_better_text(existing.title, result.title)
        existing.snippet = _pick_better_text(existing.snippet, result.snippet)
        existing.source = existing.source or ((result.source or "").strip() or None)
        existing.published_at = existing.published_at or ((result.published_at or "").strip() or None)
        existing.score = float(existing.score or 0.0) + float(result.score or 0.0)
        if existing.engine is None and result.engine:
            existing.engine = result.engine

    ranked = sorted(
        merged.values(),
        key=lambda item: (-(item.score or 0.0), first_seen[canonicalize_result_url(item.url)]),
    )
    for item in ranked:
        if item.score is not None:
            item.score = round(item.score, 4)
    return ranked[:limit]
