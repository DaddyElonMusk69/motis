# MOTIS Operator Configuration Guide

**Quick reference for configuring MOTIS runtime modes**

---

## TL;DR

```bash
# Development (filesystem)
MOTIS_RUNTIME_MODE=dev python -m motis_agent.server

# Platform (database)
MOTIS_RUNTIME_MODE=platform python -m motis_agent.server

# Standalone (local filesystem)
MOTIS_RUNTIME_MODE=standalone python -m motis_operator.runner
```

---

## Environment Variables

All MOTIS settings use the `MOTIS_` prefix:

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `MOTIS_RUNTIME_MODE` | `dev`, `platform`, `standalone` | `platform` | Runtime mode |
| `MOTIS_DATABASE_URL` | PostgreSQL URL | `postgresql://localhost:5432/motis` | Database connection (platform mode) |
| `MOTIS_REDIS_URL` | Redis URL | `redis://localhost:6379/0` | Redis connection (platform mode) |
| `MOTIS_OPERATORS_PATH` | File path | Auto-computed | Operators directory |
| `MOTIS_SKILLS_PATH` | File path | Auto-computed | Skills directory |
| `MOTIS_STATE_DB` | File path | Auto-computed | SQLite state DB (dev/standalone) |
| `MOTIS_MCP_EXECUTION_URL` | HTTP URL | `http://localhost:8000` | Execution MCP server |
| `MOTIS_MCP_MARKET_DATA_URL` | HTTP URL | `http://localhost:8001` | Market data MCP server |
| `MOTIS_MCP_OPERATOR_URL` | HTTP URL | `http://localhost:8002` | Operator MCP server |
| `MOTIS_OPENAI_API_KEY` | API key | - | OpenAI API key |
| `MOTIS_DEFAULT_MODEL` | Model name | `gpt-4` | Default LLM model |
| `MOTIS_HYPERLIQUID_API_KEY` | API key | - | Hyperliquid API key (standalone) |
| `MOTIS_HYPERLIQUID_SECRET` | Secret | - | Hyperliquid secret (standalone) |
| `MOTIS_BINANCE_API_KEY` | API key | - | Binance API key (standalone) |
| `MOTIS_BINANCE_SECRET` | Secret | - | Binance secret (standalone) |

---

## `.env` File Templates

### Development Mode (`.env.dev`)

```bash
MOTIS_RUNTIME_MODE=dev
MOTIS_DATABASE_URL=postgresql://localhost:5432/motis_dev
MOTIS_OPENAI_API_KEY=sk-...
MOTIS_DEFAULT_MODEL=gpt-4
```

### Platform Mode (`.env.platform`)

```bash
MOTIS_RUNTIME_MODE=platform
MOTIS_DATABASE_URL=postgresql://prod-db:5432/motis_prod
MOTIS_REDIS_URL=redis://prod-redis:6379/0
MOTIS_MCP_EXECUTION_URL=http://mcp-execution:8000
MOTIS_MCP_MARKET_DATA_URL=http://mcp-market-data:8001
MOTIS_MCP_OPERATOR_URL=http://mcp-operator:8002
```

### Standalone Mode (`~/.motis/.env`)

```bash
MOTIS_RUNTIME_MODE=standalone
MOTIS_OPERATORS_PATH=~/.motis/operators
MOTIS_SKILLS_PATH=~/.motis/skills
MOTIS_STATE_DB=~/.motis/state.db
MOTIS_HYPERLIQUID_API_KEY=...
MOTIS_HYPERLIQUID_SECRET=...
MOTIS_OPENAI_API_KEY=sk-...
MOTIS_DEFAULT_MODEL=gpt-4
```

---

## Mode Comparison

| Feature | Dev | Platform | Standalone |
|---------|-----|----------|------------|
| **Operators** | Filesystem (Git) | Database (per-user) | Filesystem (~/.motis) |
| **Skills** | Filesystem (Git) | Database (per-user) | Filesystem (~/.motis) |
| **State** | SQLite (local) | Redis (shared) | SQLite (local) |
| **MCP** | Optional | Required | Not used |
| **Database** | Optional | Required | Not used |
| **Multi-user** | No | Yes | No |
| **Hot-patching** | No | Yes | No |
| **IDE support** | Full | No | Full |
| **Version control** | Git | Export/import | Git |

---

## Quick Start

### Development Setup

```bash
# 1. Clone repo
git clone https://github.com/your-org/motis.git
cd motis

# 2. Create .env file
cat > .env << EOF
MOTIS_RUNTIME_MODE=dev
MOTIS_DATABASE_URL=postgresql://localhost:5432/motis_dev
MOTIS_OPENAI_API_KEY=sk-...
EOF

# 3. Install dependencies
pip install -e packages/operator_sdk
pip install -e services/agent

# 4. Run agent
python -m motis_agent.server
```

### Platform Deployment

```bash
# 1. Set environment variables
export MOTIS_RUNTIME_MODE=platform
export MOTIS_DATABASE_URL=postgresql://prod-db:5432/motis
export MOTIS_REDIS_URL=redis://prod-redis:6379/0

# 2. Run migrations
alembic upgrade head

# 3. Start services
docker-compose up -d

# 4. Run agent
python -m motis_agent.server
```

### Standalone Installation

```bash
# 1. Install MOTIS agent
pip install motis-agent

# 2. Initialize config
motis init

# 3. Edit ~/.motis/.env
nano ~/.motis/.env

# 4. Run agent
motis run
```

---

## Troubleshooting

### "Database connection failed" (Platform mode)

Check `MOTIS_DATABASE_URL` is set and database is running:
```bash
echo $MOTIS_DATABASE_URL
psql $MOTIS_DATABASE_URL -c "SELECT 1"
```

### "Operators not found" (Dev mode)

Check `MOTIS_OPERATORS_PATH` points to correct directory:
```bash
echo $MOTIS_OPERATORS_PATH
ls -la $MOTIS_OPERATORS_PATH
```

### "MCP server unreachable" (Platform mode)

Check MCP servers are running:
```bash
curl $MOTIS_MCP_EXECUTION_URL/health
curl $MOTIS_MCP_MARKET_DATA_URL/health
curl $MOTIS_MCP_OPERATOR_URL/health
```

### "Exchange API key invalid" (Standalone mode)

Check credentials are set:
```bash
echo $MOTIS_HYPERLIQUID_API_KEY
echo $MOTIS_BINANCE_API_KEY
```

---

## Advanced Configuration

### Custom Paths

```bash
# Use custom operator directory
MOTIS_RUNTIME_MODE=dev \
MOTIS_OPERATORS_PATH=/custom/path/operators \
python -m motis_agent.server
```

### Multiple Environments

```bash
# Development
python -m motis_agent.server --env-file=.env.dev

# Staging
python -m motis_agent.server --env-file=.env.staging

# Production
python -m motis_agent.server --env-file=.env.prod
```

### Docker Compose

```yaml
services:
  agent:
    image: motis-agent:latest
    env_file:
      - .env.platform
    environment:
      MOTIS_RUNTIME_MODE: platform
    volumes:
      - ./config:/app/config
```

---

## See Also

- [Operator System Design](./operator-system.md) - Complete architecture
- [MCP Strategy](../motis_mcp_strategy.md) - MCP server architecture
- [MOTIS PRD](../motis_prd.md) - Product requirements

---

**End of Configuration Guide**
