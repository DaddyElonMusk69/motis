# Quant Strategy Desk

> Stock screening + factor research in parallel → strategy backtest → risk audit.

**Type:** research
**Asset Class:** quantitative_equity
**Exchange:** 
**Trigger:** manual

## What It Does

Stock screening + factor research in parallel → strategy backtest → risk audit. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `screener` - Stock Screener
- `factor_miner` - Factor Researcher
- `backtester` - Strategy Backtester
- `risk_auditor` - Risk Auditor

## Graph Shape

```
screener + factor_miner + backtester -> risk_auditor
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `goal`.

## Variables

- `market` - Target market
- `goal` - Strategy objective (e.g., momentum + value dual factor)
