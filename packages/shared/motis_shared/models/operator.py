from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from motis_shared.types import (
    AUMClass,
    AssetClass,
    Exchange,
    OperatorState,
    OperatorTrigger,
    StrategyStyle,
)


class RiskConfig(BaseModel):
    """Operator-level risk rules (user/agent defined)."""

    max_position_size_pct: float = Field(
        default=10.0,
        description="Max single position as % of operator capital",
        ge=0.1,
        le=100.0,
    )
    max_daily_loss_pct: float = Field(
        default=5.0,
        description="Daily loss kill-switch as % of operator capital",
        ge=0.1,
        le=50.0,
    )
    max_leverage: float = Field(default=3.0, ge=1.0, le=100.0)
    stop_loss_pct: Optional[float] = Field(
        default=None, description="Default SL % if operator doesn't set per-trade SL"
    )
    take_profit_pct: Optional[float] = Field(default=None)
    max_open_positions: int = Field(default=5, ge=1, le=50)
    allowed_assets: list[str] = Field(
        default_factory=list,
        description="Whitelist of symbols. Empty = all assets allowed.",
    )


class TriggerConfig(BaseModel):
    """How and when the operator is scheduled to run."""

    type: OperatorTrigger = OperatorTrigger.TIME_BASED
    interval_seconds: Optional[int] = Field(
        default=60, description="For TIME_BASED triggers"
    )
    cron_expression: Optional[str] = Field(
        default=None, description="Cron string for complex schedules"
    )
    event_filter: Optional[dict[str, Any]] = Field(
        default=None, description="For EVENT_BASED triggers"
    )


class ModelConfig(BaseModel):
    """BYOM: which model to use for reasoning nodes in this operator."""

    base_url: str = Field(description="OpenAI-compatible base URL")
    api_key_ref: str = Field(
        description="Reference to encrypted key in user's model config"
    )
    model_name: str


class OperatorModel(BaseModel):
    """Full operator definition stored in DB."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: str
    description: str = ""
    state: OperatorState = OperatorState.DRAFT
    version: int = 1

    # Strategy metadata
    asset_class: AssetClass
    strategy_style: StrategyStyle
    asset_universe: list[str] = Field(
        description="List of symbols this operator trades, e.g. ['BTC-USDT', 'ETH-USDT']"
    )
    exchange: Exchange

    # Configuration
    risk_config: RiskConfig = Field(default_factory=RiskConfig)
    trigger_config: TriggerConfig = Field(default_factory=TriggerConfig)
    model_config_override: Optional[ModelConfig] = None  # None = use platform default

    # Graph definition
    graph_spec_url: Optional[str] = Field(
        default=None, description="S3/R2 URL to serialized LangGraph spec"
    )

    # Linked exchange connection
    exchange_connection_id: Optional[UUID] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OperatorSummary(BaseModel):
    """Lightweight view for sidebar / API list endpoints."""

    id: UUID
    name: str
    state: OperatorState
    asset_class: AssetClass
    exchange: Exchange
    current_pnl_pct: Optional[float] = None
    current_pnl_usd: Optional[float] = None
    aum_usd: Optional[float] = None
    aum_class: Optional[AUMClass] = None
    updated_at: datetime
