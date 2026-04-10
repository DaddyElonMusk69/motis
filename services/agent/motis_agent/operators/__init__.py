"""
Motis Operators
===============
Each operator lives in its own folder with an ``operator.py`` entry point
that exports the operator contract: STATE, MANIFEST, build_graph().

Directory layout::

    operators/
    ├── examples/           # Reference implementations (dev/learning)
    │   └── btc_smc_long/
    │       └── operator.py
    ├── builtin/            # Production-ready operators (ported from vibe trading)
    │   └── smc_swing/
    │       └── operator.py
    └── user/               # Agent-generated operators (runtime, gitignored in dev)
        └── my_strategy/
            └── operator.py

Each operator folder may also contain:
    - prompts/     — hot-patchable prompt templates for REASON nodes
    - config.yaml  — operator-specific overrides
    - tests/       — operator-level tests

The OperatorRegistry (in core/operator_registry.py) scans all three
subdirectories and loads any folder containing a valid operator.py.

Contract reference: docs/operators/02-contract-and-validation.md
"""
