# Derivatives Strategy Desk

> Volatility analysis → strategy design → Greeks risk management: sequential options trading desk workflow.

**Type:** research
**Asset Class:** derivatives
**Exchange:** 
**Trigger:** manual

## What It Does

Volatility analysis → strategy design → Greeks risk management: sequential options trading desk workflow. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `vol_analyst` - Volatility Analyst
- `strategy_designer` - Strategy Designer
- `greeks_manager` - Greeks Risk Manager

## Graph Shape

```
vol_analyst -> strategy_designer -> greeks_manager
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `target`, `view`.

## Variables

- `target` - Underlying (e.g.: BTC, CSI 300 ETF, AAPL)
- `view` - Market view (bullish / bearish / neutral / long volatility / short volatility)
