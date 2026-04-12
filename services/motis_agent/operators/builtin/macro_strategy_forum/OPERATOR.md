# Macro Strategy Forum

> Global + domestic + policy perspectives run in parallel; chief strategist delivers integrated cross-asset allocation guidance.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

Global + domestic + policy perspectives run in parallel; chief strategist delivers integrated cross-asset allocation guidance. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `global_economist` - Global Economist
- `domestic_economist` - China Economist
- `policy_analyst` - Policy Analyst
- `chief_strategist` - Chief Strategist

## Graph Shape

```
global_economist + domestic_economist + policy_analyst -> chief_strategist
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `horizon`.

## Variables

- `market` - Focus market (e.g., A-shares, Hong Kong, global multi-asset, crypto)
- `horizon` - Horizon (e.g., monthly, quarterly, annual)
