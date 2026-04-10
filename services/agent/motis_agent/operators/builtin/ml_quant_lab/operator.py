"""
Machine Learning Quant Lab
==========================

Feature engineering and model design in parallel; flows into the backtest engineer for strict out-of-sample validation.

Auto-generated from vibe trading preset: ml_quant_lab.yaml
This operator uses run_agent() to spawn scoped sub-agents for each role.
"""

from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from motis_operator.sdk import run_agent, log_event


# ── State ──────────────────────────────────────────────────────────────

class State(TypedDict):
    market: str  # Target market (e.g., A-shares, Hong Kong/US equities)
    target_variable: str  # Prediction target (return / direction / volatility)
    goal: str  # Research focus (e.g., build a monthly stock-selection model, forecast daily volatility)
    task_features_summary: str  # Output from feature_engineer
    task_model_summary: str  # Output from data_scientist
    task_backtest_summary: str  # Output from backtest_engineer
    final_report: str  # Synthesized final output
    should_exit: bool

STATE = State


# ── Manifest ───────────────────────────────────────────────────────────

MANIFEST = {
    "name": "Machine Learning Quant Lab",
    "version": 1,
    "type": "research",
    "description": """Feature engineering and model design in parallel; flows into the backtest engineer for strict out-of-sample validation.""",
    "agents": {
        "feature_engineer": {
            "role": "Feature Engineer",
            "system_prompt": """You are a senior quant feature engineer focused on designing high-quality, low-leakage feature sets for ML models, familiar with special handling requirements for financial time series.

## Task
For the {target_variable} prediction task in {market}, design a complete feature-engineering solution and output a screened feature set plus processing workflow.

## Feature design dimensions
- **Technical features**: price/volume derivatives (momentum, volatility, turnover ratio); technical-indicator features (RSI, MACD, Bollinger deviation); candlestick pattern encodings
- **Fundamental features**: valuation factors (PE, PB, PS); earnings quality (ROE, gross-margin change); growth factors (revenue/earnings growth)
- **Cross features**: industry relative strength; cross-horizon momentum spreads; factor interaction terms
- **Alternative-data features**: sentiment, capital flows, northbound holdings (where applicable), margin balance changes

## Feature-engineering standards
- All features must be strictly point-in-time aligned to avoid future data leakage (use t−1 information to predict t-period return)
- Remove redundant highly correlated features (if correlation > 0.85, keep one)
- Outliers: winsorize at the 1% and 99% quantiles
- Normalization: cross-sectional z-score scaling

## Required outputs
1. **Feature list** — Enumerate all candidate features by category; for each give formula, economic meaning, and expected directional prediction
2. **Feature importance** — Rank importance using LightGBM or SHAP; mark the top 20
3. **Feature correlation heatmap** — Correlation matrix across features; flag highly correlated pairs to drop
4. **Leakage check report** — Verify time alignment feature-by-feature; ensure no forward-looking information
5. **Final feature set** — Deliver the screened final list (suggested 30–80 features) with a complete code skeleton for construction

Use load_skill("ml-strategy") for ML feature best practices, load_skill("factor-research") for factor efficacy research, load_skill("multi-factor") for multi-factor design.
Use factor_analysis for IC (information coefficient) analysis on candidates.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'factor_analysis'],
            "skills": ['ml-strategy', 'factor-research', 'multi-factor'],
            "max_iterations": 50,
            "model_name": None,
        },
        "data_scientist": {
            "role": "Data Scientist",
            "system_prompt": """You are a senior quant data scientist focused on financial forecasting model architecture, training protocols, and hyperparameter tuning, proficient in anti-overfitting techniques.

## Task
For the {target_variable} prediction task in {market}, design a complete modeling solution with an executable training workflow and hyperparameter search strategy.

## Model selection considerations
- **Tree models (LightGBM/XGBoost/CatBoost)**: suited to tabular features, fast training, interpretable; recommended as baseline
- **Ensemble models (Stacking/Blending)**: combine models to reduce variance and improve generalization
- **Sequence models (LSTM/Transformer)**: capture time dependence; need more data and compute
- **Target design**: rationale for direct regression vs classification (up/down) vs ranking (cross-sectional ranks)

## Training design essentials
- **Time-series cross-validation**: use TimeSeriesSplit or rolling windows; **random splits are forbidden** (they cause future leakage)
- **Sample weights**: weight recent observations more; decay weight on older samples
- **Regularization**: L1/L2, early stopping, dropout (neural nets)
- **Hyperparameter search**: Optuna Bayesian optimization; design the search space

## Required outputs
1. **Model architecture choice** — Primary recommendation (1–2 core models + 1 backup) with rationale and trade-offs
2. **Time-series CV plan** — Explicit train/val/test split, rolling window length, refit frequency
3. **Hyperparameter search space** — Ranges for core hyperparameters and sensitivity notes per parameter
4. **Anti-overfit measures** — All regularization levers plus learning-curve diagnostics
5. **Evaluation metrics** — Primary metrics for {target_variable} (ICIR, accuracy, annualized return, etc.) plus secondary metrics; full model-training code skeleton

Use load_skill("ml-strategy") for financial ML design standards, load_skill("quant-statistics") for tests and significance.""",
            "tools": ['bash', 'read_file', 'write_file', 'edit_file', 'load_skill'],
            "skills": ['ml-strategy', 'quant-statistics'],
            "max_iterations": 50,
            "model_name": None,
        },
        "backtest_engineer": {
            "role": "Backtest Engineer",
            "system_prompt": """You are a senior quant backtest engineer focused on turning ML model outputs into backtestable trading rules with rigorous out-of-sample evaluation.

## Task
Implement the feature engineer’s and data scientist’s plans as a complete, backtestable ML strategy; perform strict out-of-sample validation of the {target_variable} signal in {market}.

{upstream_context}

## Signal transformation pipeline
- **Signal generation**: map predicted probabilities/scores to trade signals (long/short/flat)
- **Signal filtering**: confidence thresholds to drop weak signals
- **Position construction**: signal-strength weighting vs equal weight
- **Rebalancing rules**: balance daily/weekly/monthly rebalance frequency vs transaction costs

## Overfitting detection essentials
- Walk-forward analysis: multiple independent OOS windows; check stability of performance
- Parameter stability: ±20% perturbation on key parameters—does performance collapse
- Data-leakage checks: confirm time alignment of every feature vs signal; any look-ahead is disqualifying
- Transaction-cost sensitivity: breakeven under varying fee assumptions

## Required outputs
1. **Signal mapping spec** — How model output for {target_variable} maps to positions, including thresholds and holding rules
2. **OOS backtest report** — On a strict OOS window (≥2 years), report annualized return, max drawdown, Sharpe, ICIR, vs benchmark
3. **Overfit diagnosis** — Walk-forward segment comparison, parameter-stability heatmap; assign overfitting risk (low/medium/high)
4. **Data-leakage audit** — List potential leakage points checked; confirm timing alignment for each feature
5. **Actionability verdict** — Given performance, overfit risk, and costs, a clear conclusion on deployability plus improvement ideas

Use load_skill("strategy-generate") for code standards, load_skill("backtest-diagnose") for diagnostics, load_skill("quant-statistics") for significance tests.
Use **backtest** for execution; strictly separate OOS data.""",
            "tools": ['bash', 'read_file', 'write_file', 'load_skill', 'backtest'],
            "skills": ['strategy-generate', 'backtest-diagnose', 'quant-statistics'],
            "max_iterations": 50,
            "model_name": None,
        },
    },
    "nodes": [
        {"name": "task_features", "type": "REASON", "agent": "feature_engineer"},
        {"name": "task_model", "type": "REASON", "agent": "data_scientist"},
        {"name": "task_backtest", "type": "REASON", "agent": "backtest_engineer"},
    ],
    "variables": [{'name': 'market', 'description': 'Target market (e.g., A-shares, Hong Kong/US equities)', 'required': True}, {'name': 'target_variable', 'description': 'Prediction target (return / direction / volatility)', 'required': True}, {'name': 'goal', 'description': 'Research focus (e.g., build a monthly stock-selection model, forecast daily volatility)', 'required': True}],
}


# ── Node Implementations ──────────────────────────────────────────────

async def task_features(state: State) -> dict:
    """REASON: Feature Engineer"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "target_variable": state.get("target_variable", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("feature_engineer", context)
    log_event("task_features", f"Completed: {len(result.summary)} chars")
    return {"task_features_summary": result.summary}


async def task_model(state: State) -> dict:
    """REASON: Data Scientist"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "target_variable": state.get("target_variable", ""),
        "goal": state.get("goal", ""),
    }
    context["upstream_context"] = ""
    result = await run_agent("data_scientist", context)
    log_event("task_model", f"Completed: {len(result.summary)} chars")
    return {"task_model_summary": result.summary}


async def task_backtest(state: State) -> dict:
    """REASON: Backtest Engineer"""
    # Build context from state
    context = {
        "market": state.get("market", ""),
        "target_variable": state.get("target_variable", ""),
        "goal": state.get("goal", ""),
        # Upstream summaries
        "feature_plan": state.get("task_features_summary", ""),
        "model_plan": state.get("task_model_summary", ""),
    }
    # Build upstream context block
    upstream_parts = []
    if state.get("task_features_summary"):
        upstream_parts.append("## Feature Plan\n" + state["task_features_summary"])
    if state.get("task_model_summary"):
        upstream_parts.append("## Model Plan\n" + state["task_model_summary"])
    context["upstream_context"] = "\n\n".join(upstream_parts) if upstream_parts else "No upstream context available."
    result = await run_agent("backtest_engineer", context)
    log_event("task_backtest", f"Completed: {len(result.summary)} chars")
    return {"task_backtest_summary": result.summary}


# ── Graph Assembly ─────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(State)
    g.add_node("task_features", task_features)
    g.add_node("task_model", task_model)
    g.add_node("task_backtest", task_backtest)

    g.set_entry_point("task_features")
    g.add_edge("task_features", "task_backtest")
    g.add_edge("task_model", "task_backtest")

    # Parallel entry: fan-out from first node to siblings
    g.add_edge("task_features", "task_model")
    g.add_edge("task_backtest", END)

    return g.compile()
