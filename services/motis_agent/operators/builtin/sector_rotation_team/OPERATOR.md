# Sector Rotation Research Team

> Economic cycle + prosperity + capital flows in parallel → rotation strategist builds and backtests a sector rotation strategy.

**Type:** research
**Asset Class:** equity
**Exchange:** 
**Trigger:** manual

## What It Does

Economic cycle + prosperity + capital flows in parallel → rotation strategist builds and backtests a sector rotation strategy. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `cycle_analyst` - Economic Cycle Analyst
- `prosperity_analyst` - Sector Prosperity Analyst
- `flow_analyst` - Capital Flow Analyst
- `rotation_strategist` - Sector Rotation Strategist

## Graph Shape

```
cycle_analyst + prosperity_analyst + flow_analyst -> rotation_strategist
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `goal`.

## Variables

- `market` - Target market (default A-shares; can specify HK/US)
- `goal` - Focus theme (e.g. new energy, tech growth, high dividend, exporters)
