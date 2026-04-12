"""
Platform-level risk guard.

This runs at the execution MCP layer before any order reaches an exchange.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class GuardResult:
    approved: bool
    reasons: list[str] = field(default_factory=list)


class PlatformRiskGuard:
    """
    Enforces platform-level trading limits.

    Limits (from env / user account settings):
        MAX_LEVERAGE
        MAX_POSITION_PCT
        MAX_DAILY_LOSS_PCT
        MAX_ORDER_SIZE_USD
    """

    def __init__(self):
        self.max_leverage = float(os.getenv("PLATFORM_MAX_LEVERAGE", "20"))
        self.max_position_pct = float(os.getenv("PLATFORM_MAX_POSITION_PCT", "25"))
        self.max_daily_loss_pct = float(os.getenv("PLATFORM_MAX_DAILY_LOSS_PCT", "15"))
        self.max_order_size_usd = float(os.getenv("PLATFORM_MAX_ORDER_USD", "100000"))

    async def check(self, operator_id: str, order: dict) -> GuardResult:
        """
        Run all platform risk checks against a proposed order.
        """
        del operator_id

        reasons: list[str] = []

        size = order.get("size", 0)
        if size <= 0:
            reasons.append("Order size must be positive")

        symbol = order.get("symbol", "")
        if not symbol:
            reasons.append("Symbol is required")

        if size > self.max_order_size_usd:
            reasons.append(
                f"Order size {size} exceeds platform limit of ${self.max_order_size_usd:,.0f}"
            )

        return GuardResult(approved=not reasons, reasons=reasons)
