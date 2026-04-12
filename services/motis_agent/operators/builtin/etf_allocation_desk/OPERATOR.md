# ETF Allocation Desk

> ETF screening + macro allocation + risk budgeting three-dimensional parallel analysis → portfolio optimizer constructs the final ETF portfolio and backtests.

**Type:** research
**Asset Class:** etf
**Exchange:** 
**Trigger:** manual

## What It Does

ETF screening + macro allocation + risk budgeting three-dimensional parallel analysis → portfolio optimizer constructs the final ETF portfolio and backtests. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `etf_screener` - ETF Screener
- `macro_allocator` - Macro Allocator
- `risk_budgeter` - Risk Budgeter
- `portfolio_optimizer` - Portfolio Optimizer

## Graph Shape

```
etf_screener + macro_allocator + risk_budgeter -> portfolio_optimizer
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `risk_profile`, `market`.

## Variables

- `risk_profile` - Risk profile (conservative / balanced / aggressive)
- `market` - Target market (default: A-shares; options: global multi-asset, HK/US equities, A-shares + HK)
