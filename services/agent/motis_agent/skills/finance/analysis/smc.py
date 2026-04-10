"""
Smart Money Concepts (SMC) analysis skills.

These implement ICT/SMC methodology including:
  - Break of Structure (BOS)
  - Change of Character (CHoCH)
  - Liquidity Sweeps
  - Order Blocks
  - Fair Value Gaps (FVG)

Based on the smc skill from Vibe-Trading, extended with the
market structure analysis work from the Vegas Tunnel agent project.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd
import numpy as np


class MarketStructurePoint:
    """A significant high or low in market structure."""
    def __init__(self, index: int, price: float, kind: str, timestamp):
        self.index = index
        self.price = price
        self.kind = kind  # "HH", "HL", "LH", "LL"
        self.timestamp = timestamp

    def __repr__(self):
        return f"MSP({self.kind} @ {self.price:.4f})"


def detect_swing_points(
    df: pd.DataFrame,
    left_bars: int = 5,
    right_bars: int = 5,
) -> tuple[list, list]:
    """
    Detect swing highs and swing lows using a pivot point algorithm.

    Args:
        df: OHLCV DataFrame with columns: open, high, low, close, volume
        left_bars: Number of bars to the left for pivot confirmation
        right_bars: Number of bars to the right for pivot confirmation

    Returns:
        (swing_highs, swing_lows) — lists of (index, price) tuples
    """
    highs, lows = [], []
    for i in range(left_bars, len(df) - right_bars):
        if all(df["high"].iloc[i] >= df["high"].iloc[i - left_bars:i]) and \
           all(df["high"].iloc[i] >= df["high"].iloc[i + 1:i + right_bars + 1]):
            highs.append((i, df["high"].iloc[i], df.index[i]))
        if all(df["low"].iloc[i] <= df["low"].iloc[i - left_bars:i]) and \
           all(df["low"].iloc[i] <= df["low"].iloc[i + 1:i + right_bars + 1]):
            lows.append((i, df["low"].iloc[i], df.index[i]))
    return highs, lows


def detect_bos(
    df: pd.DataFrame,
    swing_left: int = 5,
    swing_right: int = 5,
) -> list[dict]:
    """
    Break of Structure (BOS) detection.
    A BOS confirms trend continuation when price breaks a previous swing.

    Returns a list of BOS events:
        { index, price, direction ("bullish"|"bearish"), broken_swing_price, timestamp }
    """
    highs, lows = detect_swing_points(df, swing_left, swing_right)
    bos_events = []

    # Bullish BOS: price closes above a previous swing high
    for i, (hi_idx, hi_price, hi_ts) in enumerate(highs):
        subsequent = df.iloc[hi_idx + 1:]
        if len(subsequent) == 0:
            continue
        break_candle = subsequent[subsequent["close"] > hi_price]
        if not break_candle.empty:
            first = break_candle.iloc[0]
            bos_events.append({
                "index": break_candle.index[0],
                "price": float(first["close"]),
                "direction": "bullish",
                "broken_swing_price": hi_price,
                "broken_swing_ts": hi_ts,
                "timestamp": break_candle.index[0],
            })

    # Bearish BOS: price closes below a previous swing low
    for lo_idx, lo_price, lo_ts in lows:
        subsequent = df.iloc[lo_idx + 1:]
        if len(subsequent) == 0:
            continue
        break_candle = subsequent[subsequent["close"] < lo_price]
        if not break_candle.empty:
            first = break_candle.iloc[0]
            bos_events.append({
                "index": break_candle.index[0],
                "price": float(first["close"]),
                "direction": "bearish",
                "broken_swing_price": lo_price,
                "broken_swing_ts": lo_ts,
                "timestamp": break_candle.index[0],
            })

    return sorted(bos_events, key=lambda e: e["index"])


def detect_choch(
    df: pd.DataFrame,
    swing_left: int = 5,
    swing_right: int = 5,
) -> list[dict]:
    """
    Change of Character (CHoCH) detection.
    A CHoCH signals a potential trend reversal by breaking the opposing swing.

    Returns a list of CHoCH events with direction and confidence.
    """
    highs, lows = detect_swing_points(df, swing_left, swing_right)
    choch_events = []

    # Bullish CHoCH (in downtrend): price breaks above the most recent Lower High
    if lows and highs:
        recent_lower_high = sorted([h for h in highs], key=lambda x: x[0])
        for i, (lh_idx, lh_price, lh_ts) in enumerate(recent_lower_high[:-1]):
            next_high = recent_lower_high[i + 1]
            if next_high[1] < lh_price:  # Confirms lower high structure
                subsequent = df.iloc[next_high[0] + 1:]
                break_candle = subsequent[subsequent["close"] > lh_price]
                if not break_candle.empty:
                    choch_events.append({
                        "index": break_candle.index[0],
                        "direction": "bullish",
                        "broken_level": lh_price,
                        "timestamp": break_candle.index[0],
                        "confidence": 0.7,
                    })

    return choch_events


def detect_liquidity_sweep(
    df: pd.DataFrame,
    swing_left: int = 5,
    swing_right: int = 5,
    wick_threshold_pct: float = 0.3,
) -> list[dict]:
    """
    Detect liquidity sweeps — price briefly breaks a swing level then reverses.
    These are stop-hunt patterns that often precede the real move.

    Args:
        wick_threshold_pct: Min wick size as % of candle range to qualify as a sweep
    """
    highs, lows = detect_swing_points(df, swing_left, swing_right)
    sweeps = []

    for hi_idx, hi_price, hi_ts in highs:
        subsequent = df.iloc[hi_idx + 1: hi_idx + 6]  # Look within 5 bars
        for idx, row in subsequent.iterrows():
            wick_above = row["high"] - max(row["open"], row["close"])
            candle_range = row["high"] - row["low"]
            if candle_range == 0:
                continue
            if row["high"] > hi_price and row["close"] < hi_price:
                if wick_above / candle_range >= wick_threshold_pct:
                    sweeps.append({
                        "index": idx,
                        "type": "bearish_sweep",  # Swept buyside liquidity
                        "swept_level": hi_price,
                        "wick_high": float(row["high"]),
                        "close": float(row["close"]),
                        "timestamp": idx,
                    })

    for lo_idx, lo_price, lo_ts in lows:
        subsequent = df.iloc[lo_idx + 1: lo_idx + 6]
        for idx, row in subsequent.iterrows():
            wick_below = min(row["open"], row["close"]) - row["low"]
            candle_range = row["high"] - row["low"]
            if candle_range == 0:
                continue
            if row["low"] < lo_price and row["close"] > lo_price:
                if wick_below / candle_range >= wick_threshold_pct:
                    sweeps.append({
                        "index": idx,
                        "type": "bullish_sweep",  # Swept sellside liquidity
                        "swept_level": lo_price,
                        "wick_low": float(row["low"]),
                        "close": float(row["close"]),
                        "timestamp": idx,
                    })

    return sorted(sweeps, key=lambda s: s["index"])


def detect_order_blocks(
    df: pd.DataFrame,
    lookback: int = 50,
) -> list[dict]:
    """
    Detect Order Blocks — the last bearish candle before a bullish impulse
    (bullish OB) or the last bullish candle before a bearish impulse (bearish OB).
    """
    order_blocks = []
    for i in range(1, min(lookback, len(df) - 3)):
        # Bullish OB: bearish candle followed by 3+ bullish candles that close higher
        if df["close"].iloc[i] < df["open"].iloc[i]:  # Bearish candle
            next_3 = df.iloc[i + 1: i + 4]
            if len(next_3) == 3 and all(next_3["close"] > next_3["open"]):
                if next_3["close"].iloc[-1] > df["high"].iloc[i]:
                    order_blocks.append({
                        "index": df.index[i],
                        "type": "bullish_ob",
                        "top": float(df["open"].iloc[i]),
                        "bottom": float(df["close"].iloc[i]),
                        "timestamp": df.index[i],
                        "mitigated": False,
                    })

        # Bearish OB: bullish candle followed by 3+ bearish candles
        if df["close"].iloc[i] > df["open"].iloc[i]:  # Bullish candle
            next_3 = df.iloc[i + 1: i + 4]
            if len(next_3) == 3 and all(next_3["close"] < next_3["open"]):
                if next_3["close"].iloc[-1] < df["low"].iloc[i]:
                    order_blocks.append({
                        "index": df.index[i],
                        "type": "bearish_ob",
                        "top": float(df["close"].iloc[i]),
                        "bottom": float(df["open"].iloc[i]),
                        "timestamp": df.index[i],
                        "mitigated": False,
                    })

    return order_blocks


def detect_fvg(df: pd.DataFrame) -> list[dict]:
    """
    Detect Fair Value Gaps (FVG) / Imbalances.
    A FVG exists when candle[i].low > candle[i-2].high (bullish)
    or candle[i].high < candle[i-2].low (bearish).
    """
    fvgs = []
    for i in range(2, len(df)):
        # Bullish FVG
        if df["low"].iloc[i] > df["high"].iloc[i - 2]:
            fvgs.append({
                "index": df.index[i],
                "type": "bullish_fvg",
                "top": float(df["low"].iloc[i]),
                "bottom": float(df["high"].iloc[i - 2]),
                "timestamp": df.index[i],
                "filled": False,
            })
        # Bearish FVG
        if df["high"].iloc[i] < df["low"].iloc[i - 2]:
            fvgs.append({
                "index": df.index[i],
                "type": "bearish_fvg",
                "top": float(df["low"].iloc[i - 2]),
                "bottom": float(df["high"].iloc[i]),
                "timestamp": df.index[i],
                "filled": False,
            })
    return fvgs
