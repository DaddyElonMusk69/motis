"""Provider protocols and fallback adapters for Motis Data MCP."""

from __future__ import annotations

from typing import Protocol

from motis_data_mcp.contracts import (
    ReadUrlRequest,
    ToolEnvelope,
    WebCrawlRequest,
    WebExtractRequest,
    WebSearchRequest,
    build_not_implemented_envelope,
)


class WebSearchProvider(Protocol):
    name: str

    async def search(self, request: WebSearchRequest) -> ToolEnvelope:
        ...


class WebExtractProvider(Protocol):
    name: str

    async def extract(self, request: WebExtractRequest, *, tool_name: str) -> ToolEnvelope:
        ...


class WebCrawlProvider(Protocol):
    name: str

    async def crawl(self, request: WebCrawlRequest) -> ToolEnvelope:
        ...


class StubSearchProvider:
    def __init__(self, name: str, message: str) -> None:
        self.name = name
        self._message = message

    async def search(self, request: WebSearchRequest) -> ToolEnvelope:
        return build_not_implemented_envelope(
            tool="web_search",
            provider=self.name,
            request={
                "query": request.query,
                "limit": request.limit,
                "vertical": request.vertical,
                "sort_by": request.sort_by,
                "allowed_domains": request.allowed_domains,
                "blocked_domains": request.blocked_domains,
                "max_age_hours": request.max_age_hours,
                "region": request.region,
                "include_content": request.include_content,
            },
            message=self._message,
        )


class StubExtractProvider:
    def __init__(self, name: str, message: str) -> None:
        self.name = name
        self._message = message

    async def extract(self, request: WebExtractRequest, *, tool_name: str) -> ToolEnvelope:
        return build_not_implemented_envelope(
            tool=tool_name,
            provider=self.name,
            request={
                "urls": request.urls,
                "format": request.format,
                "prompt": request.prompt,
                "max_chars_per_url": request.max_chars_per_url,
                "timeout_seconds": request.timeout_seconds,
            },
            message=self._message,
        )


class StubCrawlProvider:
    def __init__(self, name: str, message: str) -> None:
        self.name = name
        self._message = message

    async def crawl(self, request: WebCrawlRequest) -> ToolEnvelope:
        return build_not_implemented_envelope(
            tool="web_crawl",
            provider=self.name,
            request={
                "root_url": request.root_url,
                "prompt": request.prompt,
                "mode": request.mode,
                "max_pages": request.max_pages,
                "same_domain_only": request.same_domain_only,
                "allowed_domains": request.allowed_domains,
                "blocked_domains": request.blocked_domains,
            },
            message=self._message,
        )


def single_url_to_extract_request(request: ReadUrlRequest) -> WebExtractRequest:
    return WebExtractRequest(
        urls=[request.url],
        format=request.format,
        prompt=request.prompt,
        max_chars_per_url=request.max_chars,
        timeout_seconds=request.timeout_seconds,
    )
