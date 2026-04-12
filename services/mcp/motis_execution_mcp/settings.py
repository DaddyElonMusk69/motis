"""
Settings for the HTTP-facing Motis Execution MCP service.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionMCPSettings:
    agent_mcp_secret: str = os.getenv("AGENT_MCP_SECRET", "dev-secret-change-in-prod")
    host: str = os.getenv("MOTIS_EXECUTION_MCP_HOST", "0.0.0.0")
    port: int = int(os.getenv("MOTIS_EXECUTION_MCP_PORT", "8003"))
    log_level: str = os.getenv("MOTIS_EXECUTION_MCP_LOG_LEVEL", "info")


settings = ExecutionMCPSettings()
