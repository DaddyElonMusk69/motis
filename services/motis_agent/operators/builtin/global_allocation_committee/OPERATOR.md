# Global Allocation Committee

> Parallel A-shares + crypto + HK/US analysts; allocator synthesizes cross-market allocation with data-driven weighting, scenario analysis, and rebalancing rules.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

Parallel A-shares + crypto + HK/US analysts; allocator synthesizes cross-market allocation with data-driven weighting, scenario analysis, and rebalancing rules. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `a_share_analyst` - A-Share Analyst
- `crypto_analyst` - Crypto Analyst
- `us_hk_analyst` - HK / US Analyst
- `allocator` - Allocation Strategist

## Graph Shape

```
a_share_analyst + crypto_analyst + us_hk_analyst -> allocator
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `goal`, `risk_tolerance`.

## Variables

- `goal` - Investment objective (e.g., Q2 2026 multi-asset allocation)
- `risk_tolerance` - Risk tolerance (conservative / moderate / aggressive)
