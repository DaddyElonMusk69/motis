# Geopolitical Risk War Room

> Geopolitical analysis, energy shock, and supply-chain impact run in parallel, then feed into the Chief Strategist for synthesis, producing emergency asset-allocation playbooks for geopolitical crises.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

Geopolitical analysis, energy shock, and supply-chain impact run in parallel, then feed into the Chief Strategist for synthesis, producing emergency asset-allocation playbooks for geopolitical crises. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `geopolitical_analyst` - Geopolitical Analyst
- `energy_analyst` - Energy Shock Analyst
- `supply_chain_analyst` - Supply Chain Analyst
- `chief_strategist` - Chief Strategist

## Graph Shape

```
geopolitical_analyst + energy_analyst + supply_chain_analyst -> chief_strategist
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `crisis`, `market`.

## Variables

- `crisis` - Crisis narrative (e.g., Taiwan Strait escalation, Hormuz blockade, full Red Sea Houthi disruption)
- `market` - Focus market (e.g., A-shares, Hong Kong, global multi-asset)
