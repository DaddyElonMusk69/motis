# Market Sentiment Intelligence Unit

> News intel / social sentiment / capital flows in parallel → sentiment signal synthesizer outputs composite score and reversal signals.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

News intel / social sentiment / capital flows in parallel → sentiment signal synthesizer outputs composite score and reversal signals. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `news_analyst` - News Intelligence Analyst
- `social_analyst` - Social Sentiment Analyst
- `flow_analyst` - Capital Flow Analyst
- `signal_synthesizer` - Sentiment Signal Synthesizer

## Graph Shape

```
news_analyst + social_analyst + flow_analyst -> signal_synthesizer
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `timeframe`.

## Variables

- `market` - Target market, e.g. A-shares / HK / US / crypto / CSI 300
- `timeframe` - Horizon: daily or weekly
