# Upstream Quarantine

This package holds upstream-derived carry-overs that are **not** part of the
live Motis agent runtime.

Why they are here:

- they were imported or adapted from the upstream foundation
- they still depend on upstream namespaces or assumptions
- they are useful reference material during extraction
- they should not quietly shape the production runtime while we are still
  defining Motis-owned replacements

Rule:

- do not add new production imports from this package
- extract logic from here into `motis_agent/core/` deliberately
- once a Motis-owned replacement exists, delete the quarantined copy

Current contents:

- `compression.py`
- `model.py`
- `trajectory.py`

