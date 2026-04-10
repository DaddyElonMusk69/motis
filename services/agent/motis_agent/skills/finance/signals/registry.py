"""Signal engine registry — discover and instantiate signal engines by name."""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, Type

logger = logging.getLogger(__name__)

# Module paths for each engine
_ENGINE_MODULES: Dict[str, str] = {
    "smc": "motis_agent.skills.finance.signals.smc",
    "technical": "motis_agent.skills.finance.signals.technical",
    "ichimoku": "motis_agent.skills.finance.signals.ichimoku",
    "candlestick": "motis_agent.skills.finance.signals.candlestick",
    "volatility": "motis_agent.skills.finance.signals.volatility",
    "harmonic": "motis_agent.skills.finance.signals.harmonic",
    "elliott_wave": "motis_agent.skills.finance.signals.elliott_wave",
    "multi_factor": "motis_agent.skills.finance.signals.multi_factor",
    "pair_trading": "motis_agent.skills.finance.signals.pair_trading",
    "seasonal": "motis_agent.skills.finance.signals.seasonal",
}


def list_engines() -> list[str]:
    """Return names of all registered signal engines."""
    return sorted(_ENGINE_MODULES.keys())


def get_engine(name: str, **kwargs: Any) -> Any:
    """Instantiate a signal engine by name.

    Args:
        name: Engine name (e.g. 'smc', 'technical', 'ichimoku').
        **kwargs: Constructor arguments passed to SignalEngine().

    Returns:
        Instantiated SignalEngine.

    Raises:
        KeyError: If engine name not found.
        ImportError: If engine module can't be imported (missing dependency).
    """
    if name not in _ENGINE_MODULES:
        raise KeyError(f"Unknown signal engine '{name}'. Available: {list_engines()}")

    module_path = _ENGINE_MODULES[name]
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ImportError(
            f"Signal engine '{name}' requires missing dependency: {e}. "
            f"Install it and try again."
        ) from e

    engine_cls = getattr(module, "SignalEngine", None)
    if engine_cls is None:
        raise AttributeError(f"Module {module_path} has no SignalEngine class")

    return engine_cls(**kwargs)
