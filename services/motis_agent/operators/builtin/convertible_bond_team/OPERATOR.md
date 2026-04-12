# Convertible Bond Research Team

> Parallel three-dimensional analysis — bond floor, equity optionality, and embedded option value — synthesized into a convertible bond investment strategy.

**Type:** research
**Asset Class:** convertible_bond
**Exchange:** 
**Trigger:** manual

## What It Does

Parallel three-dimensional analysis — bond floor, equity optionality, and embedded option value — synthesized into a convertible bond investment strategy. It runs as a scoped multi-agent operator inside Motis and returns a consolidated output the master agent can use directly.

## Agents

- `bond_analyst` - Bond Floor Analyst
- `equity_analyst` - Underlying Equity Analyst
- `option_analyst` - Embedded Option Analyst
- `cb_strategist` - Convertible Bond Strategist

## Graph Shape

```
bond_analyst + equity_analyst + option_analyst -> cb_strategist
```

## When To Use

Use when the user wants this workflow as a reusable operator instead of a one-off chat answer. It works best when the request naturally includes inputs like `market`, `goal`, `strategy_type`.

## Variables

- `market` - Target market (default: A-share convertible bonds)
- `goal` - Research focus (e.g.: uncover undervalued convertibles, position for conversion price reset candidates)
- `strategy_type` - Strategy type (low-price / dual-low / high-convexity / rotation; leave blank for strategist's discretion)
