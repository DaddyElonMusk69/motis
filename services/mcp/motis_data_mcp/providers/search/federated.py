"""Federated Motis-native provider for web search."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from motis_data_mcp.contracts import (
    SearchEngineFailure,
    ToolEnvelope,
    WebSearchPayload,
    WebSearchRequest,
    WebSearchResult,
    build_tool_envelope,
    payload_dict,
)
from motis_data_mcp.providers.search.core import (
    SearchEngineExecutor,
    assign_engine_scores,
    decorate_search_request,
    distribute_limit,
    merge_search_results,
    resolve_engine_names,
)
from motis_data_mcp.providers.search.engines import SEARCH_ENGINE_REGISTRY

DEFAULT_SEARCH_ENGINES = "ddg,startpage,bing"


def _build_payload(
    request: WebSearchRequest,
    *,
    engines: Sequence[str],
    results: Sequence[WebSearchResult],
    partial_failures: Sequence[SearchEngineFailure],
) -> dict:
    return payload_dict(
        WebSearchPayload(
            query=request.query,
            limit=request.limit,
            vertical=request.vertical,
            sort_by=request.sort_by,
            results=list(results),
            total_results=len(results),
            engines=list(engines),
            partial_failures=list(partial_failures),
        )
    )


class FederatedSearchProvider:
    """Multi-engine search provider with Motis-owned aggregation and ranking."""

    name = "motis_search"

    def __init__(
        self,
        *,
        engines: Sequence[str] | None = None,
        engine_registry: Mapping[str, SearchEngineExecutor] | None = None,
    ) -> None:
        configured = engines or os.getenv("MOTIS_WEB_SEARCH_ENGINES", DEFAULT_SEARCH_ENGINES)
        resolved = resolve_engine_names(configured)
        self._engines = tuple(resolved or resolve_engine_names(DEFAULT_SEARCH_ENGINES))
        self._engine_registry = dict(engine_registry or SEARCH_ENGINE_REGISTRY)

    async def _run_engine(
        self,
        engine: str,
        *,
        request: WebSearchRequest,
        query: str,
        limit: int,
    ) -> tuple[list[WebSearchResult], SearchEngineFailure | None]:
        executor = self._engine_registry.get(engine)
        if executor is None:
            return [], SearchEngineFailure(
                engine=engine,
                code="unsupported_engine",
                message=f"Unsupported search engine: {engine}",
            )

        if limit <= 0:
            return [], None

        try:
            results = await executor(request, query, limit)
        except ImportError as exc:
            return [], SearchEngineFailure(
                engine=engine,
                code="dependency_missing",
                message=str(exc) or f"Missing dependency for search engine: {engine}",
            )
        except Exception as exc:
            return [], SearchEngineFailure(
                engine=engine,
                code="engine_error",
                message=str(exc),
            )

        return assign_engine_scores(engine, results), None

    async def search(self, request: WebSearchRequest) -> ToolEnvelope:
        query, warnings = decorate_search_request(request)
        limits = distribute_limit(request.limit, len(self._engines))
        partial_failures: list[SearchEngineFailure] = []
        aggregated_results: list[WebSearchResult] = []

        executed_engines = 0
        for engine, limit in zip(self._engines, limits, strict=False):
            engine_results, failure = await self._run_engine(
                engine,
                request=request,
                query=query,
                limit=limit,
            )
            if limit > 0:
                executed_engines += 1
            aggregated_results.extend(engine_results)
            if failure is not None:
                partial_failures.append(failure)

        merged_results = merge_search_results(aggregated_results, limit=request.limit)
        payload = _build_payload(
            request,
            engines=self._engines,
            results=merged_results,
            partial_failures=partial_failures,
        )

        if partial_failures:
            failed_engines = ", ".join(failure.engine for failure in partial_failures)
            warnings.append(f"Some search engines failed and were skipped: {failed_engines}.")

        if merged_results or not partial_failures:
            return build_tool_envelope(
                tool="web_search",
                provider=self.name,
                warnings=warnings,
                data=payload,
            )

        error_code = "dependency_missing" if all(failure.code == "dependency_missing" for failure in partial_failures) else "provider_error"
        if executed_engines <= 0:
            error_code = "provider_error"

        return build_tool_envelope(
            tool="web_search",
            provider=self.name,
            status="error",
            warnings=warnings,
            data=payload,
            error={
                "code": error_code,
                "message": "All configured search engines failed to return results.",
            },
        )
