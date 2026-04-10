"""
Motis Operator Package
=======================
Operators are autonomous LangGraph agents that run trading strategies.

This package contains:
- registry.py  — Mode-aware operator registry (dev=filesystem, platform=DB)
- base.py      — OperatorBase class for hand-coded operators
- state.py     — BaseOperatorState and shared Pydantic models
- operators/   — Operator modules (each exports STATE, MANIFEST, build_graph)

Design reference: docs/operators/
"""
