# Machine Learning Quant Lab

> Feature engineering and model design in parallel; flows into the backtest engineer for strict out-of-sample validation.

**Type:** research
**Asset Class:** quantitative_equity
**Exchange:** 
**Trigger:** manual

## What It Does

Feature engineering and model design in parallel; flows into the backtest engineer for strict out-of-sample validation. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `feature_engineer` - Feature Engineer
- `data_scientist` - Data Scientist
- `backtest_engineer` - Backtest Engineer

## Graph Shape

```
feature_engineer + data_scientist -> backtest_engineer
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `target_variable`, `goal`.

## Variables

- `market` - Target market (e.g., A-shares, Hong Kong/US equities)
- `target_variable` - Prediction target (return / direction / volatility)
- `goal` - Research focus (e.g., build a monthly stock-selection model, forecast daily volatility)
