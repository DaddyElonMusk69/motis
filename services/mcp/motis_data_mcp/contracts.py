"""
Structured contracts for Motis Data MCP networking tools.

The agent-facing tool names remain compatibility-friendly (`web_search`,
`web_extract`, `read_url`), but the request and response models are Motis-
owned so providers can be swapped without changing the operator surface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

SEARCH_VERTICALS = (
    "general",
    "news",
    "finance",
    "company",
    "filings",
    "macro",
    "crypto",
    "defi",
    "docs",
)

SEARCH_SORT_ORDERS = ("relevance", "recent")
READ_FORMATS = ("markdown", "text", "html", "json")
CRAWL_MODES = ("extract", "map")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_request_id() -> str:
    return f"mdmcp_{uuid4().hex[:12]}"


@dataclass(slots=True)
class WebSearchRequest:
    query: str
    limit: int = 5
    vertical: str = "general"
    sort_by: str = "relevance"
    allowed_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)
    max_age_hours: int | None = None
    region: str | None = None
    include_content: bool = False


@dataclass(slots=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str | None = None
    published_at: str | None = None
    score: float | None = None
    engine: str | None = None


@dataclass(slots=True)
class SearchEngineFailure:
    engine: str
    code: str
    message: str


@dataclass(slots=True)
class WebSearchPayload:
    query: str
    limit: int
    vertical: str
    sort_by: str
    results: list[WebSearchResult] = field(default_factory=list)
    total_results: int | None = None
    engines: list[str] = field(default_factory=list)
    partial_failures: list[SearchEngineFailure] = field(default_factory=list)


@dataclass(slots=True)
class WebExtractRequest:
    urls: list[str]
    format: str = "markdown"
    prompt: str | None = None
    max_chars_per_url: int | None = 20000
    timeout_seconds: int = 30


@dataclass(slots=True)
class ReadUrlRequest:
    url: str
    format: str = "markdown"
    prompt: str | None = None
    max_chars: int | None = 20000
    timeout_seconds: int = 30


@dataclass(slots=True)
class WebDocument:
    url: str
    final_url: str | None = None
    title: str | None = None
    source: str | None = None
    content_type: str | None = None
    status_code: int | None = None
    excerpt: str | None = None
    content: str | None = None
    published_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WebExtractPayload:
    documents: list[WebDocument] = field(default_factory=list)


@dataclass(slots=True)
class WebCrawlRequest:
    root_url: str
    prompt: str | None = None
    mode: str = "extract"
    max_pages: int = 5
    same_domain_only: bool = True
    allowed_domains: list[str] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WebCrawlPayload:
    root_url: str
    mode: str
    pages: list[WebDocument] = field(default_factory=list)
    discovered_urls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolEnvelope:
    status: str
    tool: str
    provider: str
    data: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
    service: str = "motis_data_mcp"
    request_id: str = field(default_factory=build_request_id)
    as_of: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def payload_dict(payload: Any) -> dict[str, Any]:
    return asdict(payload)


def build_tool_envelope(
    *,
    tool: str,
    provider: str,
    data: dict[str, Any],
    status: str = "ok",
    warnings: list[str] | None = None,
    error: dict[str, Any] | None = None,
) -> ToolEnvelope:
    return ToolEnvelope(
        status=status,
        tool=tool,
        provider=provider,
        data=data,
        warnings=list(warnings or []),
        error=error,
    )


def build_not_implemented_envelope(
    *,
    tool: str,
    provider: str,
    request: dict[str, Any],
    message: str,
) -> ToolEnvelope:
    return build_tool_envelope(
        tool=tool,
        provider=provider,
        status="not_implemented",
        data={"request": request},
        error={"code": "not_implemented", "message": message},
    )


def build_validation_error_envelope(
    *,
    tool: str,
    request: dict[str, Any],
    message: str,
) -> ToolEnvelope:
    return build_tool_envelope(
        tool=tool,
        provider="motis_contract",
        status="error",
        data={"request": request},
        error={"code": "validation_error", "message": message},
    )
