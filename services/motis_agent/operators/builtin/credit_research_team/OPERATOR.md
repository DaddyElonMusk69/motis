# Fixed Income Credit Research Team

> Credit quality + interest rate environment + sector credit three-dimensional parallel analysis → fixed income strategist synthesizes a complete bond investment strategy.

**Type:** research
**Asset Class:** fixed_income
**Exchange:** 
**Trigger:** manual

## What It Does

Credit quality + interest rate environment + sector credit three-dimensional parallel analysis → fixed income strategist synthesizes a complete bond investment strategy. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `credit_analyst` - Credit Analyst
- `rate_analyst` - Interest Rate Analyst
- `sector_credit_analyst` - Sector Credit Analyst
- `fixed_income_strategist` - Fixed Income Strategist

## Graph Shape

```
credit_analyst + rate_analyst + sector_credit_analyst -> fixed_income_strategist
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `target`, `market`.

## Variables

- `target` - Research subject or sector (e.g.: a specific LGFV platform, the property sector, steel bonds, AA-rated credit bond portfolio)
- `market` - Bond market (default: China bond market; options: credit bonds / LGFV bonds / rate bonds / convertible bonds)
