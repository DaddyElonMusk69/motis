# Motis

> Finance- and trading-oriented AI agent platform.

## Repo Map

```
Motis/
├── packages/
│   └── shared/          # Pydantic models, types, utils (shared across all services)
├── services/
│   ├── motis_agent/        # Master agent runtime, local CLI, skills, operators
│   ├── mcp/                # Data, execution, and operator MCP boundaries
│   ├── platform/           # Platform API, DB schema, and runtime scaffolding
│   └── upstream/           # Imported source material being folded into Motis
├── web/                    # Next.js frontend
├── infra/                  # Containerized stack definitions
├── scripts/                # Bootstrap, smoke, and import helpers
└── docs/                   # PRD, operator docs, architecture notes
```

## Current Local Workflow

The repo-root commands are centered on the Motis surfaces that are already in use:

- bootstrapping the Python workspace
- starting local Postgres and Redis
- running the Motis agent service and CLI
- running the checked-in test suite

## Quick Start

```bash
make bootstrap
cp services/motis_agent/.env.example services/motis_agent/.env
# Add your OpenAI-compatible provider settings to services/motis_agent/.env
make up
make db-migrate
make agent
```

In another terminal:

```bash
make chat
```

The repo-root `.env.example` is kept for shared workspace settings and container-oriented workflows. For day-to-day agent work, the most important local defaults live in `services/motis_agent/.env.example`.

## Development

```bash
# Bootstrap or refresh the workspace
make bootstrap

# Start local infrastructure
make up

# Apply platform migrations
make db-migrate

# Run the Motis agent service
make agent

# Run the local CLI
make chat

# Browse or resume local CLI conversations
.venv/bin/motis-chat --list-sessions
.venv/bin/motis-chat --resume latest

# Run tests
uv run pytest
```

Workflow: open feature branches and send PRs into `main`. We are using a trunk-based flow by default rather than a long-lived `dev` branch.

## Docs

- [PRD](docs/motis_prd.md)
- [Architecture Research](docs/design/01-architecture-research.md)
- [Operator Architecture](docs/operators/01-architecture-overview.md)
- [Operator Configuration](docs/operators/05-configuration-guide.md)
- [MCP Strategy](docs/architecture/motis_mcp_strategy.md)
- [Motis Agent Service](services/motis_agent/README.md)
- [Contributing](CONTRIBUTING.md)
