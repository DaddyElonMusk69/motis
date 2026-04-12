# Pairs Trading Research Lab

> Correlation scan and cointegration testing in parallel → converge into the pair strategist for strategy design → final microstructure review for execution feasibility.

**Type:** research
**Asset Class:** statistical_arb
**Exchange:** 
**Trigger:** manual

## What It Does

Correlation scan and cointegration testing in parallel → converge into the pair strategist for strategy design → final microstructure review for execution feasibility. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `correlation_scanner` - Correlation Scanner
- `cointegration_tester` - Cointegration Tester
- `pair_strategist` - Pair Strategist
- `microstructure_reviewer` - Microstructure Reviewer

## Graph Shape

```
correlation_scanner + cointegration_tester + pair_strategist -> microstructure_reviewer
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `sector`.

## Variables

- `market` - Target market (e.g. A-shares, Hong Kong, US, crypto)
- `sector` - Sector filter (e.g. banks, consumer, semis); empty = full market
