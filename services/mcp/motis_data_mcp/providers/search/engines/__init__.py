"""Engine registry for Motis federated search."""

from motis_data_mcp.providers.search.core import SearchEngineExecutor
from motis_data_mcp.providers.search.engines.bing import search_bing
from motis_data_mcp.providers.search.engines.ddg import search_ddg
from motis_data_mcp.providers.search.engines.startpage import search_startpage

SEARCH_ENGINE_REGISTRY: dict[str, SearchEngineExecutor] = {
    "ddg": search_ddg,
    "startpage": search_startpage,
    "bing": search_bing,
}

__all__ = ["SEARCH_ENGINE_REGISTRY"]
