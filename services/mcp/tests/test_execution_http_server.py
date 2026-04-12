from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from motis_execution_mcp import http_server


def test_health_reports_http_transport():
    client = TestClient(http_server.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["transport"] == "http"


def test_call_tool_rejects_missing_agent_token():
    client = TestClient(http_server.app)

    response = client.post(
        "/tools/get_positions",
        json={"operator_id": "op_123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid X-Agent-Token"


def test_call_tool_unwraps_dispatch_payload(monkeypatch):
    client = TestClient(http_server.app)

    async def fake_dispatch_execution(name: str, args: dict):
        assert name == "get_positions"
        assert args == {"operator_id": "op_123"}
        return [
            type(
                "FakeTextContent",
                (),
                {
                    "text": json.dumps(
                        {
                            "status": "ok",
                            "service": "motis_execution_mcp",
                            "tool": "get_positions",
                            "data": {"positions": [{"symbol": "BTCUSDT"}]},
                        }
                    )
                },
            )()
        ]

    monkeypatch.setattr(http_server, "dispatch_execution", fake_dispatch_execution)

    response = client.post(
        "/tools/get_positions",
        json={"operator_id": "op_123"},
        headers={"X-Agent-Token": "dev-secret-change-in-prod"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "motis_execution_mcp",
        "tool": "get_positions",
        "data": {"positions": [{"symbol": "BTCUSDT"}]},
    }
