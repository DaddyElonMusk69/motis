# Event-Driven Task Force

> Event scanning → deep impact analysis → strategy construction: sequential deep-dive chain replicating an event-driven hedge fund special investigation unit workflow.

**Type:** research
**Asset Class:** event_driven_equity
**Exchange:** 
**Trigger:** manual

## What It Does

Event scanning → deep impact analysis → strategy construction: sequential deep-dive chain replicating an event-driven hedge fund special investigation unit workflow. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `event_scanner` - Event Scout
- `impact_analyst` - Impact Analyst
- `strategy_builder` - Strategy Builder

## Graph Shape

```
event_scanner -> impact_analyst -> strategy_builder
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `event_type`.

## Variables

- `market` - Target market, e.g.: A-shares / Hong Kong / US equities / Chinese ADRs
- `event_type` - Event type filter, e.g.: M&A / insider trading / earnings / policy / litigation / management change; enter 'all types' for no filter
