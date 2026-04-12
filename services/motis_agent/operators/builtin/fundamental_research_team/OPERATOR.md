# Fundamental Deep Research Team

> Financial / valuation / quality three-dimensional parallel analysis → research editor consolidates into a buy-side deep research report.

**Type:** research
**Asset Class:** equity
**Exchange:** 
**Trigger:** manual

## What It Does

Financial / valuation / quality three-dimensional parallel analysis → research editor consolidates into a buy-side deep research report. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `financial_analyst` - Financial Analyst
- `valuation_analyst` - Valuation Analyst
- `quality_analyst` - Quality Analyst
- `report_editor` - Research Report Editor

## Graph Shape

```
financial_analyst + valuation_analyst + quality_analyst -> report_editor
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `target`, `market`.

## Variables

- `target` - Research subject (stock code or name, e.g.: 600519 Kweichow Moutai)
- `market` - Market (e.g.: A-shares, Hong Kong, US equities)
