"""
Motis Agent Service — Settings
================================
All configuration via environment variables (12-factor).
Loaded once at import time. Validated by pydantic-settings.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ───────────────────────────────────────────────────────────────
    # asyncpg driver required: postgresql+asyncpg://...
    database_url: str = "postgresql+asyncpg://motis:motis@localhost:5432/motis"

    # ── Inter-service auth ─────────────────────────────────────────────────────
    # Shared secret between agent service and MCP service.
    # Platform gateway injects requests; MCP verifies X-Agent-Token header.
    agent_mcp_secret: str = "dev-secret-change-in-prod"

    # ── MCP service URL ────────────────────────────────────────────────────────
    mcp_url: str = "http://localhost:8002"

    # ── Tool defaults ──────────────────────────────────────────────────────────
    # Max turns before the agent loop exits with max_turns_exceeded
    agent_max_turns: int = 40

    # Brave Search API key (for web_search tool)
    brave_api_key: str = ""
    # Tavily API key (fallback web search)
    tavily_api_key: str = ""

    # ── Terminal sandbox ───────────────────────────────────────────────────────
    terminal_timeout_seconds: int = 30
    # Phase 0: "subprocess" (restricted). Phase 1: "docker"
    terminal_backend: str = "subprocess"


settings = Settings()
