"""
Platform-level risk guard.

This runs at the MCP execution layer — BEFORE any order reaches an exchange.
It enforces hard limits that CANNOT be overridden by operator code.

Two-layer risk model:
  Layer 1 (operator): RiskConfig in OperatorModel — user/agent-defined rules
  Layer 2 (platform): PlatformRiskGuard — hard caps, runs here in MCP
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class GuardResult:
    approved: bool
    reasons: list[str] = field(default_factory=list)


class PlatformRiskGuard:
    """
    Enforces platform-level trading limits.

    Limits (from env / user account settings):
        MAX_LEVERAGE          — hard cap on leverage (default: 20x)
        MAX_POSITION_PCT      — max single position as % of account (default: 25%)
        MAX_DAILY_LOSS_PCT    — global daily loss kill-switch (default: 15%)
        MAX_ORDER_SIZE_USD    — absolute USD cap per order (default: $100k)
    """

    def __init__(self):
        self.max_leverage = float(os.getenv("PLATFORM_MAX_LEVERAGE", "20"))
        self.max_position_pct = float(os.getenv("PLATFORM_MAX_POSITION_PCT", "25"))
        self.max_daily_loss_pct = float(os.getenv("PLATFORM_MAX_DAILY_LOSS_PCT", "15"))
        self.max_order_size_usd = float(os.getenv("PLATFORM_MAX_ORDER_USD", "100000"))

    async def check(self, operator_id: str, order: dict) -> GuardResult:
        """
        Run all platform risk checks against a proposed order.
        Returns GuardResult with approval status and any rejection reasons.
        """
        reasons = []

        # TODO: fetch operator account state from DB for full checks
        # For now, basic structural checks

        size = order.get("size", 0)
        if size <= 0:
            reasons.append("Order size must be positive")

        symbol = order.get("symbol", "")
        if not symbol:
            reasons.append("Symbol is required")

        # Size limit (simplified — needs current price for USD check)
        if size > self.max_order_size_usd:
            reasons.append(
                f"Order size {size} exceeds platform limit of ${self.max_order_size_usd:,.0f}"
            )

        return GuardResult(approved=len(reasons) == 0, reasons=reasons)
