# Global Equities Research Desk

> Cross-market equity research: A-share analyst + HK/US analyst + crypto analyst + global strategist. Covers fundamental screening, earnings analysis, ETF flows, and cross-listing arbitrage for multi-market stock selection.

**Type:** research
**Asset Class:** global_equity
**Exchange:** 
**Trigger:** manual

## What It Does

Cross-market equity research: A-share analyst + HK/US analyst + crypto analyst + global strategist. Covers fundamental screening, earnings analysis, ETF flows, and cross-listing arbitrage for multi-market stock selection. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `a_share_researcher` - A-Share Equity Researcher
- `us_hk_researcher` - US & HK Equity Researcher
- `crypto_researcher` - Crypto Asset Researcher
- `global_strategist` - Global Equity Strategist

## Graph Shape

```
a_share_researcher + us_hk_researcher + crypto_researcher -> global_strategist
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `goal`, `risk_tolerance`.

## Variables

- `goal` - Investment objective (e.g., Q2 2026 global equity allocation, tech sector deep-dive)
- `risk_tolerance` - Risk tolerance level (conservative / moderate / aggressive)
