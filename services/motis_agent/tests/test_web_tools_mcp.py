from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

import tools.web_tools as web_tools


def test_web_search_tool_routes_through_data_mcp(monkeypatch) -> None:
    calls = []

    def fake_call(tool_name: str, payload: dict, *, session_id: str | None = None) -> dict:
        calls.append((tool_name, payload, session_id))
        return {
            "status": "ok",
            "service": "motis_data_mcp",
            "tool": "web_search",
            "provider": "ddg_search",
            "warnings": [],
            "error": None,
            "data": {
                "query": payload["query"],
                "results": [
                    {
                        "title": "Latest CPI release",
                        "url": "https://www.bls.gov/news.release/cpi.nr0.htm",
                        "snippet": "Consumer Price Index news release.",
                        "source": "www.bls.gov",
                    }
                ],
            },
        }

    monkeypatch.setattr(web_tools, "_call_data_mcp_sync", fake_call)
    monkeypatch.setattr(web_tools._debug, "log_call", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_tools._debug, "save", lambda *args, **kwargs: None)

    raw = web_tools.web_search_tool("latest CPI", limit=2, session_id="sess_123")
    payload = json.loads(raw)

    assert calls == [("web_search", {"query": "latest CPI", "limit": 2}, "sess_123")]
    assert payload["success"] is True
    assert payload["data"]["total_results"] == 1
    assert payload["data"]["web"][0]["description"] == "Consumer Price Index news release."


def test_web_extract_tool_routes_through_data_mcp(monkeypatch) -> None:
    calls = []

    async def fake_call(tool_name: str, payload: dict, *, session_id: str | None = None) -> dict:
        calls.append((tool_name, payload, session_id))
        return {
            "status": "ok",
            "service": "motis_data_mcp",
            "tool": "web_extract",
            "provider": "http_reader",
            "warnings": [],
            "error": None,
            "data": {
                "documents": [
                    {
                        "url": "https://example.com/report",
                        "final_url": "https://example.com/report",
                        "title": "Example Report",
                        "content": "hello world",
                        "metadata": {},
                    }
                ]
            },
        }

    monkeypatch.setattr(web_tools, "_call_data_mcp_async", fake_call)
    monkeypatch.setattr(web_tools, "is_safe_url", lambda url: True)
    monkeypatch.setattr(web_tools, "check_website_access", lambda url: None)
    monkeypatch.setattr(web_tools._debug, "log_call", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_tools._debug, "save", lambda *args, **kwargs: None)

    raw = asyncio.run(
        web_tools.web_extract_tool(
            ["https://example.com/report"],
            format="markdown",
            use_llm_processing=False,
            session_id="sess_456",
        )
    )
    payload = json.loads(raw)

    assert calls == [
        (
            "web_extract",
            {
                "urls": ["https://example.com/report"],
                "format": "markdown",
                "max_chars_per_url": 20_000,
                "timeout_seconds": 30,
            },
            "sess_456",
        )
    ]
    assert payload["success"] is True
    assert payload["data"]["documents"][0]["content"] == "hello world"
    assert payload["results"][0]["content"] == "hello world"


def test_check_web_api_key_requires_configured_data_mcp_url(monkeypatch) -> None:
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.delenv("MCP_URL", raising=False)

    assert web_tools.check_web_api_key() is False


def test_data_mcp_url_falls_back_to_mcp_url(monkeypatch) -> None:
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.setenv("MCP_URL", "http://localhost:8002/")

    assert web_tools._get_data_mcp_url() == "http://localhost:8002"


def test_sync_data_mcp_http_call_disables_trust_env(monkeypatch) -> None:
    monkeypatch.setattr(web_tools, "_get_data_mcp_url", lambda: "http://localhost:8002")

    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "ok"}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(web_tools.httpx, "post", fake_post)

    payload = web_tools._call_data_mcp_sync("web_search", {"query": "fed dot plot"})

    assert payload == {"status": "ok"}
    assert captured["url"] == "http://localhost:8002/tools/web_search"
    assert captured["trust_env"] is False


def test_sync_data_mcp_http_call_requires_configured_url(monkeypatch) -> None:
    monkeypatch.setattr(web_tools, "_get_data_mcp_url", lambda: "")

    with pytest.raises(ValueError, match="DATA_MCP_URL"):
        web_tools._call_data_mcp_sync("web_search", {"query": "fed dot plot"})


def test_async_data_mcp_http_call_disables_trust_env(monkeypatch) -> None:
    monkeypatch.setattr(web_tools, "_get_data_mcp_url", lambda: "http://localhost:8002")

    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "ok"}

    class _FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, **kwargs):
            captured["url"] = url
            captured["post_kwargs"] = kwargs
            return _FakeResponse()

    monkeypatch.setattr(web_tools.httpx, "AsyncClient", _FakeAsyncClient)

    payload = asyncio.run(web_tools._call_data_mcp_async("web_search", {"query": "fed dot plot"}))

    assert payload == {"status": "ok"}
    assert captured["url"] == "http://localhost:8002/tools/web_search"
    assert captured["client_kwargs"] == {
        "timeout": web_tools._DATA_MCP_TIMEOUT,
        "follow_redirects": True,
        "trust_env": False,
    }


def test_web_crawl_tool_routes_through_data_mcp(monkeypatch) -> None:
    calls = []

    async def fake_call(tool_name: str, payload: dict, *, session_id: str | None = None) -> dict:
        calls.append((tool_name, payload, session_id))
        return {
            "status": "ok",
            "service": "motis_data_mcp",
            "tool": "web_crawl",
            "provider": "motis_crawler",
            "warnings": [],
            "error": None,
            "data": {
                "root_url": payload["root_url"],
                "mode": payload["mode"],
                "pages": [
                    {
                        "url": "https://example.com/docs",
                        "final_url": "https://example.com/docs",
                        "title": "Example Docs",
                        "content": "hello world",
                        "metadata": {},
                    }
                ],
            },
        }

    monkeypatch.setattr(web_tools, "_call_data_mcp_async", fake_call)
    monkeypatch.setattr(web_tools, "is_safe_url", lambda url: True)
    monkeypatch.setattr(web_tools, "check_website_access", lambda url: None)
    monkeypatch.setattr(web_tools._debug, "log_call", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_tools._debug, "save", lambda *args, **kwargs: None)

    raw = asyncio.run(
        web_tools.web_crawl_tool(
            "example.com",
            "Find docs",
            depth="advanced",
            use_llm_processing=False,
        )
    )
    payload = json.loads(raw)

    assert calls == [
        (
            "web_crawl",
            {
                "root_url": "https://example.com",
                "prompt": "Find docs",
                "mode": "extract",
                "max_pages": 20,
                "same_domain_only": True,
            },
            None,
        )
    ]
    assert payload["success"] is True
    assert payload["results"][0]["title"] == "Example Docs"
    assert payload["results"][0]["content"] == "hello world"
