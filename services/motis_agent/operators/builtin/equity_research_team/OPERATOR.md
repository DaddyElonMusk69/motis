# Equity Research Team

> Macro → sector → stock three-tier deep research → research editor consolidates into a complete report.

**Type:** research
**Asset Class:** equity
**Exchange:** 
**Trigger:** manual

## What It Does

Macro → sector → stock three-tier deep research → research editor consolidates into a complete report. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `macro_analyst` - Macro Analyst
- `sector_analyst` - Sector Analyst
- `stock_picker` - Stock Analyst
- `aggregator` - Research Report Editor

## Graph Shape

```
macro_analyst -> sector_analyst -> stock_picker -> aggregator
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `goal`.

## Variables

- `market` - Target market (e.g.: A-shares, Hong Kong, Crypto)
- `goal` - Research focus (e.g.: Q2 2026 outlook, opportunities in the new energy sector)
