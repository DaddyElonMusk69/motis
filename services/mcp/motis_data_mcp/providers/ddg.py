"""DuckDuckGo-backed provider for Motis web search."""

from __future__ import annotations

from motis_data_mcp.contracts import (
    ToolEnvelope,
    WebSearchPayload,
    WebSearchRequest,
    build_tool_envelope,
    payload_dict,
)
from motis_data_mcp.providers.search.core import assign_engine_scores, decorate_search_request
from motis_data_mcp.providers.search.engines.ddg import search_ddg


def _empty_payload(request: WebSearchRequest) -> dict:
    return payload_dict(
        WebSearchPayload(
            query=request.query,
            limit=request.limit,
            vertical=request.vertical,
            sort_by=request.sort_by,
            results=[],
            total_results=0,
            engines=["ddg"],
            partial_failures=[],
        )
    )


class DDGSearchProvider:
    """DuckDuckGo package-backed provider using the same DDGS path as Vibe Trading."""

    name = "ddg_search"

    async def search(self, request: WebSearchRequest) -> ToolEnvelope:
        query, warnings = decorate_search_request(request)
        try:
            results = await search_ddg(request, query, request.limit)
            results = assign_engine_scores("ddg", results)
        except ImportError:
            return build_tool_envelope(
                tool="web_search",
                provider=self.name,
                status="error",
                warnings=warnings,
                data=_empty_payload(request),
                error={
                    "code": "dependency_missing",
                    "message": "DuckDuckGo search package not installed. Install `ddgs` for web_search.",
                },
            )
        except Exception as exc:
            return build_tool_envelope(
                tool="web_search",
                provider=self.name,
                status="error",
                warnings=warnings,
                data=_empty_payload(request),
                error={
                    "code": "provider_error",
                    "message": str(exc),
                },
            )

        return build_tool_envelope(
            tool="web_search",
            provider=self.name,
            warnings=warnings,
            data=payload_dict(
                WebSearchPayload(
                    query=request.query,
                    limit=request.limit,
                    vertical=request.vertical,
                    sort_by=request.sort_by,
                    results=results,
                    total_results=len(results),
                    engines=["ddg"],
                    partial_failures=[],
                )
            ),
        )
