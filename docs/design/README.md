# Motis Design Documents

Canonical design specifications for the Motis platform. These documents are the
source of truth for architectural decisions, system contracts, and integration patterns.

## Documents

| # | Document | Description | Status |
|---|---|---|---|
| 1 | [Architecture Research](./01-architecture-research.md) | Pre-PRD survey of Hermes, Vibe Trading, and Claude Managed Agents. Key decisions on what to fork, what to mount via MCP, and what to skip. | **Final** |
| 2 | [Operator System](./02-operator-system.md) | The operator contract (STATE + MANIFEST + build_graph), 5 node types, Quality Gate, lifecycle state machine, SDK surface, standalone execution model. | **Final** |
| 3 | [Skill Integration](./03-skill-integration.md) | How Vibe Trading's 68 skills map into Motis tools. The 3-layer call stack, naming conventions, implementation backlog. | **Final** |

## How to use these

- **Before building a new feature** — check if there's a design doc that covers it.
- **When onboarding** — read in order: 1 → 2 → 3. The PRD ([docs/motis_prd.md](../motis_prd.md)) is the
  product-level companion to these technical docs.
- **When making architectural changes** — update the relevant design doc first,
  then implement.

## Relationship to other docs

```
docs/
├── motis_prd.md                      ← Product requirements (what we're building)
├── design/                           ← THIS FOLDER: how we're building it
│   ├── 01-architecture-research.md   ← Technology survey + key decisions
│   ├── 02-operator-system.md         ← Operator contract + runtime + Quality Gate
│   └── 03-skill-integration.md       ← Vibe Trading → Motis skill mapping
├── adr/                              ← Architecture Decision Records (atomic)
├── diagrams/                         ← Visual diagrams
└── *.md                              ← Porting docs (operational, not design)
```
