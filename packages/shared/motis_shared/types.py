from __future__ import annotations

from enum import Enum
from typing import Literal


class OperatorState(str, Enum):
    DRAFT = "draft"
    BACKTESTED = "backtested"
    PAPER = "paper"
    LIVE = "live"
    PAUSED = "paused"
    ARCHIVED = "archived"
    COMPLETE = "complete"   # BacktestOperator / ResearchOperator on-demand runs


class AUMClass(str, Enum):
    NANO = "nano"       # < $1,000
    MICRO = "micro"     # $1,000 – $10,000
    SMALL = "small"     # $10,000 – $100,000
    MEDIUM = "medium"   # $100,000 – $1,000,000
    LARGE = "large"     # > $1,000,000

    @classmethod
    def classify(cls, aum_usd: float) -> "AUMClass":
        if aum_usd < 1_000:
            return cls.NANO
        elif aum_usd < 10_000:
            return cls.MICRO
        elif aum_usd < 100_000:
            return cls.SMALL
        elif aum_usd < 1_000_000:
            return cls.MEDIUM
        else:
            return cls.LARGE


class OperatorTrigger(str, Enum):
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    HYBRID = "hybrid"


class Exchange(str, Enum):
    HYPERLIQUID = "hyperliquid"
    BINANCE = "binance"
    BINANCE_FUTURES = "binance_futures"
    OKX = "okx"
    BYBIT = "bybit"
    CCXT = "ccxt"  # Generic CCXT exchange


class AssetClass(str, Enum):
    CRYPTO_SPOT = "crypto_spot"
    CRYPTO_PERP = "crypto_perp"
    CRYPTO_FUTURES = "crypto_futures"
    US_EQUITY = "us_equity"
    HK_EQUITY = "hk_equity"
    A_SHARE = "a_share"
    FOREX = "forex"
    FUTURES = "futures"
    OPTIONS = "options"


class StrategyStyle(str, Enum):
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    ARBITRAGE = "arbitrage"
    MARKET_NEUTRAL = "market_neutral"
    MOMENTUM = "momentum"
    MACRO = "macro"
    STATISTICAL = "statistical"
    ML_DRIVEN = "ml_driven"


class CompetitionStatus(str, Enum):
    UPCOMING = "upcoming"
    REGISTRATION = "registration"
    LIVE = "live"
    COMPLETED = "completed"


class MarketplaceListingStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    LIVE = "live"
    SUSPENDED = "suspended"
    DELISTED = "delisted"


OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop_market", "stop_limit"]
SkillCategory = Literal[
    "data", "analysis", "research", "reporting", "execution", "builtin"
]
