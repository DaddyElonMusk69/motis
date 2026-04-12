from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from motis_data_mcp import http_server


def test_health_reports_http_transport():
    client = TestClient(http_server.app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["transport"] == "http"
    assert payload["routing"]["search_provider"]
    assert "market" in payload["providers"]
    assert "research" in payload["providers"]


def test_call_tool_rejects_missing_agent_token():
    client = TestClient(http_server.app)

    response = client.post("/tools/web_search", json={"query": "fed dot plot"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid X-Agent-Token"


def test_call_tool_unwraps_dispatch_payload(monkeypatch):
    client = TestClient(http_server.app)

    async def fake_dispatch_data(name: str, args: dict):
        assert name == "web_search"
        assert args == {"query": "latest CPI print", "limit": 2}
        return [
            type(
                "FakeTextContent",
                (),
                {
                    "text": json.dumps(
                        {
                            "status": "ok",
                            "service": "motis_data_mcp",
                            "tool": "web_search",
                            "provider": "fake_provider",
                            "data": {
                                "query": "latest CPI print",
                                "results": [],
                            },
                        }
                    )
                },
            )()
        ]

    monkeypatch.setattr(http_server, "dispatch_data", fake_dispatch_data)

    response = client.post(
        "/tools/web_search",
        json={"query": "latest CPI print", "limit": 2},
        headers={"X-Agent-Token": "dev-secret-change-in-prod"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "motis_data_mcp",
        "tool": "web_search",
        "provider": "fake_provider",
        "data": {
            "query": "latest CPI print",
            "results": [],
        },
    }
