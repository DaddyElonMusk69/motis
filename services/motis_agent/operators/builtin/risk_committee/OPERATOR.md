# Risk Committee

> Drawdown, tail risk, and market regime reviews run in parallel; head of risk signs off.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

Drawdown, tail risk, and market regime reviews run in parallel; head of risk signs off. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `drawdown_analyst` - Drawdown Analyst
- `tail_risk_analyst` - Tail Risk Analyst
- `regime_detector` - Market Regime Analyst
- `aggregator` - Head of Risk

## Graph Shape

```
drawdown_analyst + tail_risk_analyst + regime_detector -> aggregator
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `goal`.

## Variables

- `goal` - Audit target (e.g., BTC position risk, CSI 300 strategy risk)
