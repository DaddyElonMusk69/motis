# Earnings Research Desk

> Earnings-focused research team: fundamental analyst + earnings revision tracker + options/event analyst + earnings strategist. Deep-dives into company financials, consensus revisions, earnings event trades, and post-earnings drift.

**Type:** research
**Asset Class:** equity
**Exchange:** 
**Trigger:** manual

## What It Does

Earnings-focused research team: fundamental analyst + earnings revision tracker + options/event analyst + earnings strategist. Deep-dives into company financials, consensus revisions, earnings event trades, and post-earnings drift. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `fundamental_analyst` - Fundamental & Filing Analyst
- `revision_tracker` - Earnings Revision & Consensus Tracker
- `event_options_analyst` - Earnings Event & Options Analyst
- `earnings_strategist` - Earnings Desk Strategist

## Graph Shape

```
fundamental_analyst + revision_tracker + event_options_analyst -> earnings_strategist
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `target`.

## Variables

- `target` - Target stock (e.g., AAPL.US, NVDA.US, 700.HK, 600519.SH)
