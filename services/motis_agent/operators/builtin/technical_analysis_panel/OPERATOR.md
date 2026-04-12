# Technical Analysis Panel

> Classic TA + Ichimoku + harmonic patterns + Elliott Wave + SMC run in parallel → signal aggregator scores consensus and resonance.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

Classic TA + Ichimoku + harmonic patterns + Elliott Wave + SMC run in parallel → signal aggregator scores consensus and resonance. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `classic_ta_analyst` - Classic Technical Analyst
- `ichimoku_analyst` - Ichimoku Analyst
- `harmonic_analyst` - Harmonic Pattern Analyst
- `wave_analyst` - Elliott Wave Analyst
- `smc_analyst` - SMC / Order-Flow Analyst
- `signal_aggregator` - Signal Aggregator (Judge)

## Graph Shape

```
classic_ta_analyst + ichimoku_analyst + harmonic_analyst + wave_analyst + smc_analyst -> signal_aggregator
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `target`, `timeframe`.

## Variables

- `target` - Symbol (e.g. 600519.SH Kweichow Moutai, BTC-USDT, AAPL)
- `timeframe` - Interval (e.g. daily, weekly, monthly, 4H)
