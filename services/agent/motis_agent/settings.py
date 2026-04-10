"""
Motis Agent Service — Settings
================================
All configuration via environment variables (12-factor).
Loaded once at import time. Validated by pydantic-settings.
"""

from __future__ import annotations

from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Runtime mode ───────────────────────────────────────────────────────────
    # Controls where operators and skills are loaded from.
    # See: docs/operators/05-configuration-guide.md
    #   dev        → filesystem (services/agent/motis_agent/operators/)
    #   platform   → PostgreSQL (multi-user, per user_id)
    #   standalone → filesystem (~/.motis/operators/)
    runtime_mode: str = "dev"

    # ── Database ───────────────────────────────────────────────────────────────
    # asyncpg driver required: postgresql+asyncpg://...
    database_url: str = "postgresql+asyncpg://motis:motis@localhost:5432/motis"

    # ── Operator + skill filesystem paths (dev / standalone) ──────────────────
    # Auto-computed from runtime_mode if not explicitly set.
    # See: docs/operators/01-architecture-overview.md §Where Operators Live
    operators_path: str = ""
    skills_path: str = ""

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

    def model_post_init(self, __context: Any) -> None:
        """Compute default paths based on runtime_mode when not explicitly set."""
        import os
        from pathlib import Path

        if not self.operators_path:
            if self.runtime_mode == "dev":
                # Resolve relative to the project root (heuristic: walk up from this file)
                project_root = Path(__file__).resolve().parents[3]  # services/agent/motis_agent/ → project root
                self.operators_path = str(project_root / "services" / "agent" / "motis_agent" / "operators")
            elif self.runtime_mode == "standalone":
                self.operators_path = str(Path.home() / ".motis" / "operators")

        if not self.skills_path:
            if self.runtime_mode == "dev":
                project_root = Path(__file__).resolve().parents[3]
                self.skills_path = str(project_root / "services" / "agent" / "motis_agent" / "skills" / "finance")
            elif self.runtime_mode == "standalone":
                self.skills_path = str(Path.home() / ".motis" / "skills")

    @property
    def is_dev(self) -> bool:
        return self.runtime_mode == "dev"

    @property
    def is_platform(self) -> bool:
        return self.runtime_mode == "platform"

    @property
    def is_standalone(self) -> bool:
        return self.runtime_mode == "standalone"


settings = Settings()
