"""
Finance skill index — all skills absorbed from Vibe-Trading + Motis originals.

Skills are auto-discovered by the SkillRegistry on startup.
Each skill is a callable with a standardized signature:
    async def skill_name(params: SkillParams, ctx: UserContext) -> SkillResult

Categories (matching Vibe-Trading's 7 categories, extended):
    data        — market data fetching (OHLCV, orderbook, fundamentals)
    analysis    — technical analysis, pattern recognition, quantitative
    research    — macro, fundamental, on-chain, news
    reporting   — report generation, Pine Script export
    execution   — order management helpers (not the actual MCP execution layer)
    builtin     — core agent skills (memory, operator management, etc.)
"""

# ── Data skills ──────────────────────────────────────────────────────────────
from motis_agent.skills.finance.data.routing import route_data_source
from motis_agent.skills.finance.data.ccxt_ohlcv import get_ohlcv_ccxt
from motis_agent.skills.finance.data.yfinance_data import get_ohlcv_yfinance
from motis_agent.skills.finance.data.akshare_data import get_ohlcv_akshare
from motis_agent.skills.finance.data.okx_market import get_okx_market_data

# ── Analysis skills ───────────────────────────────────────────────────────────
from motis_agent.skills.finance.analysis.technical import (
    calc_rsi,
    calc_macd,
    calc_bollinger_bands,
    calc_atr,
    calc_ema,
    calc_vwap,
)
from motis_agent.skills.finance.analysis.smc import (
    detect_bos,
    detect_choch,
    detect_liquidity_sweep,
    detect_order_blocks,
    detect_fvg,
)
from motis_agent.skills.finance.analysis.candlestick import detect_candlestick_patterns
from motis_agent.skills.finance.analysis.elliott_wave import label_elliott_waves
from motis_agent.skills.finance.analysis.ml_strategy import build_ml_signal

# ── Research skills ───────────────────────────────────────────────────────────
from motis_agent.skills.finance.research.macro import analyze_macro_environment
from motis_agent.skills.finance.research.onchain import get_onchain_metrics
from motis_agent.skills.finance.research.defi import get_defi_yield_data
from motis_agent.skills.finance.research.sentiment import get_market_sentiment
from motis_agent.skills.finance.research.fundamentals import (
    get_financial_statements,
    get_earnings_estimates,
)

# ── Reporting skills ──────────────────────────────────────────────────────────
from motis_agent.skills.finance.reporting.report_generate import generate_strategy_report
from motis_agent.skills.finance.reporting.pine_script import export_pine_script
from motis_agent.skills.finance.reporting.backtest_diagnose import diagnose_backtest

# ── Swarms (multi-agent research teams) ──────────────────────────────────────
from motis_agent.swarms.base import SwarmRunner

__all__ = [
    # Data
    "route_data_source",
    "get_ohlcv_ccxt",
    "get_ohlcv_yfinance",
    "get_ohlcv_akshare",
    "get_okx_market_data",
    # Analysis
    "calc_rsi", "calc_macd", "calc_bollinger_bands",
    "calc_atr", "calc_ema", "calc_vwap",
    "detect_bos", "detect_choch", "detect_liquidity_sweep",
    "detect_order_blocks", "detect_fvg",
    "detect_candlestick_patterns",
    "label_elliott_waves",
    "build_ml_signal",
    # Research
    "analyze_macro_environment",
    "get_onchain_metrics",
    "get_defi_yield_data",
    "get_market_sentiment",
    "get_financial_statements",
    "get_earnings_estimates",
    # Reporting
    "generate_strategy_report",
    "export_pine_script",
    "diagnose_backtest",
    # Swarms
    "SwarmRunner",
]
