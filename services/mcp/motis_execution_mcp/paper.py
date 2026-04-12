"""
Paper trading executor.

This is a lightweight placeholder until trade-log persistence and exchange-aware
simulation are wired in.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


class PaperTradeExecutor:
    """Simple paper-trade fill simulator."""

    async def execute(self, order: dict) -> dict[str, object]:
        fill_price = float(order.get("price") or 0.0)
        return {
            "status": "filled",
            "mode": "paper",
            "paper": True,
            "order_id": f"paper_{uuid4().hex[:12]}",
            "operator_id": order["operator_id"],
            "symbol": order["symbol"],
            "side": order["side"],
            "order_type": order["order_type"],
            "size": order["size"],
            "fill_price": fill_price,
            "reduce_only": bool(order.get("reduce_only", False)),
            "filled_at": datetime.now(timezone.utc).isoformat(),
        }
