# Factor Research Committee

> Factor mining + factor validation running in parallel → factor combination construction → backtest review: quant fund internal research review workflow.

**Type:** research
**Asset Class:** quantitative_equity
**Exchange:** 
**Trigger:** manual

## What It Does

Factor mining + factor validation running in parallel → factor combination construction → backtest review: quant fund internal research review workflow. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `factor_miner` - Factor Miner
- `factor_validator` - Factor Validator
- `factor_combiner` - Factor Combiner
- `backtest_reviewer` - Backtest Reviewer

## Graph Shape

```
factor_miner + factor_validator + factor_combiner -> backtest_reviewer
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `factor_type`.

## Variables

- `market` - Target market (e.g.: A-shares, Hong Kong, US equities)
- `factor_type` - Factor type (value / momentum / quality / growth / alternative)
