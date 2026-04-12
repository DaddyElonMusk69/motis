# Crypto Asset Research Lab

> On-chain data + DeFi protocol + market sentiment three-dimensional parallel analysis → Alpha synthesizer converges investment recommendations.

**Type:** research
**Asset Class:** crypto
**Exchange:** 
**Trigger:** manual

## What It Does

On-chain data + DeFi protocol + market sentiment three-dimensional parallel analysis → Alpha synthesizer converges investment recommendations. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `onchain_analyst` - On-Chain Data Analyst
- `defi_analyst` - DeFi Protocol Analyst
- `crypto_sentiment_analyst` - Crypto Sentiment Analyst
- `alpha_synthesizer` - Alpha Synthesizer

## Graph Shape

```
onchain_analyst + defi_analyst + crypto_sentiment_analyst -> alpha_synthesizer
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `target`, `timeframe`.

## Variables

- `target` - Target asset (e.g.: BTC / ETH / SOL; default BTC/ETH/SOL)
- `timeframe` - Analysis time horizon (short-term 1–4 weeks / medium-term 1–3 months / long-term 3–12 months)
