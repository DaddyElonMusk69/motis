# Statistical Arbitrage Desk

> Pair scanning and microstructure analysis in parallel → converge into the arbitrage strategist to build the strategy → final risk-control review.

**Type:** research
**Asset Class:** statistical_arb
**Exchange:** 
**Trigger:** manual

## What It Does

Pair scanning and microstructure analysis in parallel → converge into the arbitrage strategist to build the strategy → final risk-control review. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `pair_scanner` - Pair Scanner
- `microstructure_analyst` - Microstructure Analyst
- `arb_strategist` - Arbitrage Strategist
- `risk_monitor` - Risk Monitor

## Graph Shape

```
pair_scanner + microstructure_analyst + arb_strategist -> risk_monitor
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `goal`, `sector`.

## Variables

- `market` - Target market (e.g. A-shares, Hong Kong, crypto)
- `goal` - Research focus (e.g. CSI 300 pair book, crypto arb ideas)
- `sector` - Sector filter (e.g. banks, consumer); empty = full market
