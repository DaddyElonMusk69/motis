# Portfolio Review Board

> Performance attribution, risk review, and execution quality in parallel; CIO synthesizes into rebalance decisions.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

Performance attribution, risk review, and execution quality in parallel; CIO synthesizes into rebalance decisions. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `attribution_analyst` - Performance Attribution Analyst
- `risk_inspector` - Risk Inspector
- `execution_analyst` - Execution Quality Analyst
- `chief_investment_officer` - Chief Investment Officer

## Graph Shape

```
attribution_analyst + risk_inspector + execution_analyst -> chief_investment_officer
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `portfolio`, `review_period`, `goal`.

## Variables

- `portfolio` - Portfolio name or description (e.g., value-growth blend, CSI 300 enhanced)
- `review_period` - Review cadence (monthly / quarterly)
- `goal` - Focus of this review (e.g., assess Q1 performance, diagnose recent NAV drawdown)
