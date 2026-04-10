"""Signal engine skills — deterministic signal generators for backtesting and operators.

Each signal engine is a Python module with a `SignalEngine` class that implements:
    generate(data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]

Signal values: 1.0 = full long, -1.0 = full short, 0.0 = flat.
Fractional values represent weight (e.g. 0.5 = half position).

Usage in operators (via call_skill):
    signals = await call_skill("signals.smc", {"ohlcv": state["ohlcv"]})
    signals = await call_skill("signals.technical", {"ohlcv": state["ohlcv"], "method": "ma_cross"})

Usage in backtests:
    from motis_agent.skills.finance.signals import smc
    engine = smc.SignalEngine(swing_length=10)
    signal_map = engine.generate(data_map)

Ported from: vibe_trading/agent/src/skills/*/example_signal_engine.py
"""

from motis_agent.skills.finance.signals.registry import list_engines, get_engine

__all__ = ["list_engines", "get_engine"]
