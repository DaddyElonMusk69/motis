# Social-Media Alternative Data Team

> Twitter, Telegram, and Reddit analyzed in parallel → Alpha synthesizer extracts tradable social sentiment factors.

**Type:** research
**Asset Class:** multi_asset
**Exchange:** 
**Trigger:** manual

## What It Does

Twitter, Telegram, and Reddit analyzed in parallel → Alpha synthesizer extracts tradable social sentiment factors. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `twitter_analyst` - Twitter Analyst
- `telegram_analyst` - Telegram Analyst
- `reddit_analyst` - Reddit Analyst
- `alpha_synthesizer` - Alpha Synthesizer

## Graph Shape

```
twitter_analyst + telegram_analyst + reddit_analyst -> alpha_synthesizer
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `target`, `timeframe`.

## Variables

- `target` - Focus name or market (e.g. BTC, Tesla, A-share tech, Nasdaq)
- `timeframe` - Horizon (real-time / daily / weekly)
