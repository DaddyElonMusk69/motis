# Commodity Research Team

> Parallel deep-dive on supply and demand, synthesized by a cycle strategist into an investment thesis — DAG workflow.

**Type:** research
**Asset Class:** commodity
**Exchange:** 
**Trigger:** manual

## What It Does

Parallel deep-dive on supply and demand, synthesized by a cycle strategist into an investment thesis — DAG workflow. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `supply_analyst` - Supply Analyst
- `demand_analyst` - Demand Analyst
- `cycle_strategist` - Cycle Strategist

## Graph Shape

```
supply_analyst + demand_analyst -> cycle_strategist
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `commodity`, `horizon`.

## Variables

- `commodity` - Commodity type, e.g.: crude oil / gold / copper / iron ore / natural gas / soybeans / aluminum / rebar
- `horizon` - Investment horizon, e.g.: 1 month / 3 months / 6 months / 1 year
