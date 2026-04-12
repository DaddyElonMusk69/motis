# Fund Selection Panel

> Multi-dimensional quantitative screening → Brinson performance attribution and style analysis → FOF portfolio weight optimization, sequential professional review chain.

**Type:** research
**Asset Class:** fund
**Exchange:** 
**Trigger:** manual

## What It Does

Multi-dimensional quantitative screening → Brinson performance attribution and style analysis → FOF portfolio weight optimization, sequential professional review chain. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `fund_screener` - Fund Screener
- `attribution_analyst` - Performance Attribution Analyst
- `fof_optimizer` - FOF Portfolio Optimizer

## Graph Shape

```
fund_screener -> attribution_analyst -> fof_optimizer
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `fund_type`, `goal`.

## Variables

- `fund_type` - Fund type, e.g.: equity / bond / balanced / index-enhanced / quant hedge / QDII
- `goal` - Investment objective, e.g.: build a steady FOF portfolio with annualized return >10% and max drawdown <15%
