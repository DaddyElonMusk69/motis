# Motis

> Agentic trading platform — from idea to live, verified operator in one conversation.

## Architecture

```
Motis/
├── packages/
│   ├── shared/          # Pydantic models, types, utils (shared across all services)
│   └── operator_sdk/    # LangGraph OperatorBase + state primitives
├── services/
│   ├── agent/           # Master agent (Hermes fork, multi-user, SSE streaming)
│   │   └── motis_agent/
│   │       ├── core/           # Agentic loop, memory, skill registry
│   │       ├── skills/finance/ # 68+ finance skills (absorbed from Vibe-Trading)
│   │       └── swarms/         # Multi-agent research teams (29 presets)
│   ├── mcp/             # MCP tool server (execution chokepoint + market data)
│   └── platform/        # API gateway + operator runtime (Celery) + arena + marketplace
├── web/                 # Next.js frontend
├── infra/               # docker-compose, k8s
├── scripts/             # Dev tooling
└── docs/                # PRD, ADRs, diagrams
```

## Quick Start

```bash
cp .env.example .env
# Edit .env with your API keys
./scripts/dev.sh
```

Services:
- **Web:** http://localhost:3000
- **Platform API:** http://localhost:8000
- **Agent:** http://localhost:8001 (internal)
- **MCP:** http://localhost:8002 (internal)

## Development

```bash
# Install Python workspace (uv)
uv sync

# Run a single service
cd services/agent && uvicorn motis_agent.server:app --reload

# Run tests
uv run pytest
```

## Docs

- [PRD](docs/motis_prd.md)
- [Architecture Research](docs/motis_architecture_research.md)
