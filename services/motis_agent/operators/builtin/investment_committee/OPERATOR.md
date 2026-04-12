# Investment Committee

> Long–short debate → risk review → PM final call: buy-side fund investment committee workflow.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

Long–short debate → risk review → PM final call: buy-side fund investment committee workflow. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `bull_advocate` - Bull-side Researcher
- `bear_advocate` - Bear-side Researcher
- `risk_officer` - Chief Risk Officer
- `portfolio_manager` - Portfolio Manager

## Graph Shape

```
bull_advocate -> bear_advocate -> risk_officer -> portfolio_manager
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `target`, `market`.

## Variables

- `target` - Security (e.g., 600519.SH Kweichow Moutai, BTC-USDT, AAPL)
- `market` - Market (e.g., A-shares, Hong Kong, US, crypto)
