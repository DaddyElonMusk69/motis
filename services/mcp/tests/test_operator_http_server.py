from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from motis_operator_mcp import http_server


def test_health_reports_http_transport():
    client = TestClient(http_server.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["transport"] == "http"


def test_call_tool_rejects_missing_agent_token():
    client = TestClient(http_server.app)

    response = client.post(
        "/tools/operator_status",
        json={"operator_id": "op_456"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid X-Agent-Token"


def test_call_tool_unwraps_dispatch_payload(monkeypatch):
    client = TestClient(http_server.app)

    async def fake_dispatch_operator(name: str, args: dict):
        assert name == "operator_status"
        assert args == {"operator_id": "op_456"}
        return [
            type(
                "FakeTextContent",
                (),
                {
                    "text": json.dumps(
                        {
                            "status": "ok",
                            "service": "motis_operator_mcp",
                            "tool": "operator_status",
                            "data": {"state": "draft"},
                        }
                    )
                },
            )()
        ]

    monkeypatch.setattr(http_server, "dispatch_operator", fake_dispatch_operator)

    response = client.post(
        "/tools/operator_status",
        json={"operator_id": "op_456"},
        headers={"X-Agent-Token": "dev-secret-change-in-prod"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "motis_operator_mcp",
        "tool": "operator_status",
        "data": {"state": "draft"},
    }
