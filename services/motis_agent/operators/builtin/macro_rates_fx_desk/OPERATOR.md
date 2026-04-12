# Macro / Rates / FX Desk

> Cross-asset macro desk: global rates analyst + FX strategist + commodity/inflation analyst + macro portfolio manager. Covers central bank policy, yield curve dynamics, currency positioning, and macro-driven asset allocation.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

Cross-asset macro desk: global rates analyst + FX strategist + commodity/inflation analyst + macro portfolio manager. Covers central bank policy, yield curve dynamics, currency positioning, and macro-driven asset allocation. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `rates_analyst` - Global Rates & Yield Curve Analyst
- `fx_strategist` - FX Strategist
- `commodity_inflation_analyst` - Commodity & Inflation Analyst
- `macro_pm` - Macro Portfolio Manager

## Graph Shape

```
rates_analyst + fx_strategist + commodity_inflation_analyst -> macro_pm
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `goal`, `timeframe`.

## Variables

- `goal` - Macro investment objective (e.g., Q2 2026 cross-asset positioning, rate cycle trade)
- `timeframe` - Investment horizon (tactical 1-3 months / strategic 6-12 months)
