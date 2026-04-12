from __future__ import annotations

import sys
from pathlib import Path


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

from motis_cli import doctor


def test_collect_data_mcp_status_uses_explicit_url_and_parses_health(monkeypatch) -> None:
    monkeypatch.setenv("DATA_MCP_URL", "http://data.example/")
    monkeypatch.setenv("MCP_URL", "http://legacy.example")
    monkeypatch.setenv("AGENT_MCP_SECRET", "secret")

    def fake_fetch(url: str, *, headers: dict[str, str] | None = None):
        if url == "http://data.example/health":
            return 200, {
                "routing": {"search_provider": "federated"},
                "providers": {
                    "market": {
                        "providers": {
                            "yfinance": {"available": True},
                            "akshare": {"available": True},
                        }
                    },
                    "research": {
                        "providers": {
                            "tushare": {"token_configured": False},
                        }
                    },
                },
            }
        if url == "http://data.example/tools":
            assert headers == {"X-Agent-Token": "secret"}
            return 200, {"tools": [{"name": "market.get_ticker"}, {"name": "web_search"}]}
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(doctor, "_doctor_fetch_json", fake_fetch)

    status = doctor.collect_data_mcp_status()

    assert status["base_url"] == "http://data.example"
    assert status["secret_configured"] is True
    assert status["health_ok"] is True
    assert status["auth_ok"] is True
    assert status["tools_ok"] is True
    assert status["tool_count"] == 2
    assert status["routing"]["search_provider"] == "federated"
    assert status["providers"]["market"]["providers"]["yfinance"]["available"] is True


def test_collect_data_mcp_status_reports_auth_mismatch(monkeypatch) -> None:
    monkeypatch.delenv("DATA_MCP_URL", raising=False)
    monkeypatch.setenv("MCP_URL", "http://localhost:8002")
    monkeypatch.setenv("AGENT_MCP_SECRET", "wrong-secret")

    def fake_fetch(url: str, *, headers: dict[str, str] | None = None):
        if url == "http://localhost:8002/health":
            return 200, {"routing": {}, "providers": {}}
        if url == "http://localhost:8002/tools":
            assert headers == {"X-Agent-Token": "wrong-secret"}
            return 401, {"detail": "Invalid X-Agent-Token"}
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(doctor, "_doctor_fetch_json", fake_fetch)

    status = doctor.collect_data_mcp_status()

    assert status["base_url"] == "http://localhost:8002"
    assert status["health_ok"] is True
    assert status["auth_ok"] is False
    assert status["tools_ok"] is False
    assert any("HTTP 401" in error for error in status["errors"])
