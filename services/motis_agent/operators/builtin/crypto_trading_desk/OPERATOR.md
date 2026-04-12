# Crypto Trading & Risk Desk

> Execution-oriented crypto desk: funding/basis analyst + liquidation/microstructure analyst + on-chain/flow analyst + risk manager. Goes beyond research into position sizing, execution timing, and risk gating.

**Type:** research
**Asset Class:** crypto
**Exchange:** 
**Trigger:** manual

## What It Does

Execution-oriented crypto desk: funding/basis analyst + liquidation/microstructure analyst + on-chain/flow analyst + risk manager. Goes beyond research into position sizing, execution timing, and risk gating. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `funding_basis_analyst` - Funding Rate & Basis Analyst
- `liquidation_analyst` - Liquidation & Microstructure Analyst
- `flow_analyst` - On-Chain & Stablecoin Flow Analyst
- `desk_risk_manager` - Trading Desk Risk Manager

## Graph Shape

```
funding_basis_analyst + liquidation_analyst + flow_analyst -> desk_risk_manager
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `target`, `timeframe`.

## Variables

- `target` - Target asset (e.g., BTC-USDT, ETH-USDT, SOL-USDT)
- `timeframe` - Trading horizon (intraday / swing 1-2 weeks / position 1-3 months)
