# BTC SMC Long (Example)

> Reference BTC SMC long operator that demonstrates the contract without placing real trades.

**Type:** paper_trade
**Asset Class:** crypto_perp
**Exchange:** hyperliquid
**Trigger:** cron `*/15 * * * *`

## What It Does

This example models a Smart Money Concepts BTC long flow with market data, structure detection, entry reasoning, sizing, guard checks, and execution stages. It is a template operator for discovery and development, not a production-ready trading system.

## Graph Shape

```
fetch data -> calc smc -> analyze entry -> size position -> risk guard -> execute orders
```

## When To Use

Use when you need a reference paper-trade operator or a starting point for a real BTC SMC/ICT automation. It is best as a contract example, test fixture, or scaffold for a fuller operator.
