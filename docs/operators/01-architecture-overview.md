# 02 — Operator System Design

> **Status:** Final — v2 (baked-in risk, full autonomy, Quality Gate)
> **Created:** 2026-04-10
> **Last updated:** 2026-04-10

---

## Foundational Decisions

Three design choices that shape everything:

1. **Operators are autonomous agents.** Full import access. They can run independently of the
   master agent, the platform, or any infrastructure beyond a Python process + API keys.
   Think "LangGraph agent before OpenClaw" — not a sandboxed script.

2. **Risk management is baked in, not injected.** The platform does NOT inject guard nodes.
   Hard stop-losses, position limits, daily loss kill-switches — all part of the generated code.
   The operator owns its own safety.

3. **The Quality Gate is the critical path.** Because the platform doesn't enforce safety,
   the master agent must verify that every operator passes a mandatory checklist *before*
   it can go from draft → paper → live. This is where the rigor lives.

---

## What an Operator Actually Is

An operator is a **self-contained LangGraph StateGraph** that can:

- Fetch its own market data
- Run deterministic computations (indicators, patterns, sizing)
- Make LLM calls for reasoning (entry/exit decisions, market analysis)
- Enforce its own risk limits (hard SL, position sizing caps, daily loss kill-switch)
- Submit orders directly to exchanges
- Run on a schedule, forever, with Redis-checkpointed state

It is, in every meaningful sense, a standalone trading agent.

The master agent's job is to *author* this agent from natural language, validate it,
and then manage its lifecycle. Once deployed, the operator runs on its own.

---

## Where Operators Live

Operators exist in **one of three storage modes**, depending on the runtime environment:

### Development Mode (Filesystem)
```
packages/operator_sdk/motis_operator/operators/
├── __init__.py
├── btc_smc_long.py
├── eth_momentum.py
└── macro_research.py
```

**Purpose**: Easier development, debugging, version control  
**Who uses**: Developers building MOTIS, testing operators  
**Lifecycle**: Code lives in Git, loaded at runtime via import  
**Benefits**: IDE support, Git history, easy debugging, breakpoints

### Production Platform (Database)
```sql
CREATE TABLE operators (
    operator_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    graph_code TEXT NOT NULL,  -- Complete Python module
    state TEXT NOT NULL,        -- draft/validating/paper/live/paused/archived
    manifest JSONB NOT NULL,    -- Parsed MANIFEST for queries
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    ...
);
```

**Purpose**: Multi-user isolation, dynamic generation, hot-patching  
**Who uses**: End users on the MOTIS platform  
**Lifecycle**: Agent generates → stores in DB → runs from DB  
**Benefits**: Per-user isolation, dynamic updates, no filesystem access needed

### Standalone Mode (Filesystem)
```
~/.motis/
├── operators/
│   ├── my_btc_strategy.py
│   ├── my_eth_strategy.py
│   └── my_macro_research.py
└── skills/
    ├── custom_indicator.md
    └── custom_research.md
```

**Purpose**: Power users running MOTIS locally (no platform)  
**Who uses**: Advanced traders, developers, self-hosters  
**Lifecycle**: User writes/generates → saves locally → runs locally  
**Benefits**: Full control, no platform dependency, portable

### Skills Follow the Same Pattern

**Development**: `services/agent/motis_agent/skills/finance/`  
**Platform**: `skills` table in PostgreSQL (user_id = NULL for platform skills)  
**Standalone**: `~/.motis/skills/`

---

## The Operator Registry

The registry loads operators based on runtime mode:

```python
# packages/operator_sdk/motis_operator/registry.py

class OperatorRegistry:
    def __init__(self, mode: str):
        """
        mode: "dev" | "platform" | "standalone"
        """
        self.mode = mode
        self._operators = {}
    
    def load_operators(self, user_id: str = None):
        if self.mode == "dev":
            # Load from packages/operator_sdk/motis_operator/operators/
            self._load_from_filesystem("motis_operator.operators")
        
        elif self.mode == "platform":
            # Load from PostgreSQL operators table (scoped to user_id)
            self._load_from_database(user_id)
        
        elif self.mode == "standalone":
            # Load from ~/.motis/operators/
            self._load_from_filesystem(os.path.expanduser("~/.motis/operators"))
    
    def _load_from_filesystem(self, path: str):
        """Scan directory, import modules, validate contract"""
        for file in Path(path).glob("*.py"):
            if file.stem.startswith("_"):
                continue
            module = import_module(f"{path}.{file.stem}")
            if self._is_valid_operator(module):
                self._operators[module.MANIFEST["name"]] = module
    
    def _load_from_database(self, user_id: str):
        """Load from PostgreSQL, exec(), validate contract"""
        rows = db.query(
            "SELECT operator_id, graph_code FROM operators WHERE user_id = ?",
            user_id
        )
        for row in rows:
            namespace = {}
            exec(row["graph_code"], namespace)
            if self._is_valid_operator_namespace(namespace):
                self._operators[row["operator_id"]] = namespace
    
    def _is_valid_operator(self, module) -> bool:
        """Check module exports STATE, MANIFEST, build_graph"""
        return (
            hasattr(module, "STATE") and
            hasattr(module, "MANIFEST") and
            hasattr(module, "build_graph") and
            callable(module.build_graph)
        )
```

### Runtime Mode Configuration

The runtime mode is controlled via **environment variables**, with support for `.env` files, command-line overrides, and config files.

#### Configuration Priority (highest to lowest):

1. **Command-line arguments** (for one-off overrides)
2. **Environment variables** (for deployment-specific config)
3. **`.env` file** (for local development)
4. **Config file** (`~/.motis/config.toml` for standalone)
5. **Defaults** (hardcoded in `settings.py`)

#### Example `.env` Files

**Development Mode** (`.env.dev`):
```bash
# Development mode - operators and skills from filesystem
MOTIS_RUNTIME_MODE=dev

# Database (for testing platform features locally)
MOTIS_DATABASE_URL=postgresql://localhost:5432/motis_dev

# Optional: Override default paths
MOTIS_OPERATORS_PATH=packages/operator_sdk/motis_operator/operators
MOTIS_SKILLS_PATH=services/agent/motis_agent/skills/finance

# Model config
MOTIS_OPENAI_API_KEY=sk-...
MOTIS_DEFAULT_MODEL=gpt-4
```

**Platform Mode** (`.env.platform`):
```bash
# Platform mode - operators and skills from database
MOTIS_RUNTIME_MODE=platform

# Database (required)
MOTIS_DATABASE_URL=postgresql://prod-db:5432/motis_prod

# Redis (for state checkpointing)
MOTIS_REDIS_URL=redis://prod-redis:6379/0

# MCP servers
MOTIS_MCP_EXECUTION_URL=http://mcp-execution:8000
MOTIS_MCP_MARKET_DATA_URL=http://mcp-market-data:8001
MOTIS_MCP_OPERATOR_URL=http://mcp-operator:8002
```

**Standalone Mode** (`~/.motis/.env`):
```bash
# Standalone mode - operators and skills from ~/.motis/
MOTIS_RUNTIME_MODE=standalone

# Local paths (defaults to ~/.motis/ if not specified)
MOTIS_OPERATORS_PATH=~/.motis/operators
MOTIS_SKILLS_PATH=~/.motis/skills
MOTIS_STATE_DB=~/.motis/state.db

# Exchange credentials (for direct SDK access)
MOTIS_HYPERLIQUID_API_KEY=...
MOTIS_HYPERLIQUID_SECRET=...
MOTIS_BINANCE_API_KEY=...
MOTIS_BINANCE_SECRET=...

# Model config
MOTIS_OPENAI_API_KEY=sk-...
MOTIS_DEFAULT_MODEL=gpt-4
```

#### Settings Implementation

```python
# services/agent/motis_agent/settings.py

import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    MOTIS runtime settings with support for .env files.
    
    All settings prefixed with MOTIS_ in environment variables.
    Priority: env vars > .env file > defaults
    """
    
    # ── Runtime Mode ────────────────────────────────────────────────
    runtime_mode: Literal["dev", "platform", "standalone"] = "platform"
    
    # ── Database (platform mode only) ───────────────────────────────
    database_url: str = "postgresql://localhost:5432/motis"
    redis_url: str = "redis://localhost:6379/0"
    
    # ── Filesystem Paths (dev/standalone modes) ─────────────────────
    operators_path: str = ""  # Computed in __init__
    skills_path: str = ""     # Computed in __init__
    state_db: str = ""        # Computed in __init__
    
    # ── MCP Server URLs (platform mode only) ────────────────────────
    mcp_execution_url: str = "http://localhost:8000"
    mcp_market_data_url: str = "http://localhost:8001"
    mcp_operator_url: str = "http://localhost:8002"
    
    # ── Model Config ────────────────────────────────────────────────
    openai_api_key: str = ""
    default_model: str = "gpt-4"
    
    # ── Exchange Credentials (standalone mode only) ─────────────────
    hyperliquid_api_key: str = ""
    hyperliquid_secret: str = ""
    binance_api_key: str = ""
    binance_secret: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MOTIS_",  # All env vars prefixed with MOTIS_
        case_sensitive=False,
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Compute default paths based on runtime_mode
        if not self.operators_path:
            if self.runtime_mode == "dev":
                self.operators_path = "packages/operator_sdk/motis_operator/operators"
            elif self.runtime_mode == "standalone":
                self.operators_path = str(Path.home() / ".motis" / "operators")
        
        if not self.skills_path:
            if self.runtime_mode == "dev":
                self.skills_path = "services/agent/motis_agent/skills/finance"
            elif self.runtime_mode == "standalone":
                self.skills_path = str(Path.home() / ".motis" / "skills")
        
        if not self.state_db:
            if self.runtime_mode == "standalone":
                self.state_db = str(Path.home() / ".motis" / "state.db")
            elif self.runtime_mode == "dev":
                self.state_db = "data/dev_state.db"
    
    @property
    def is_dev(self) -> bool:
        return self.runtime_mode == "dev"
    
    @property
    def is_platform(self) -> bool:
        return self.runtime_mode == "platform"
    
    @property
    def is_standalone(self) -> bool:
        return self.runtime_mode == "standalone"


# Global settings instance
settings = Settings()
```

#### Usage Examples

```bash
# Development mode
MOTIS_RUNTIME_MODE=dev python -m motis_agent.server

# Platform mode (default)
python -m motis_agent.server

# Standalone mode with custom paths
MOTIS_RUNTIME_MODE=standalone \
MOTIS_OPERATORS_PATH=/custom/path/operators \
python -m motis_operator.runner
```

#### Docker Compose Example (Platform Mode)

```yaml
services:
  agent:
    image: motis-agent:latest
    environment:
      MOTIS_RUNTIME_MODE: platform
      MOTIS_DATABASE_URL: postgresql://db:5432/motis
      MOTIS_REDIS_URL: redis://redis:6379/0
      MOTIS_MCP_EXECUTION_URL: http://mcp-execution:8000
      MOTIS_MCP_MARKET_DATA_URL: http://mcp-market-data:8001
      MOTIS_MCP_OPERATOR_URL: http://mcp-operator:8002
    depends_on:
      - db
      - redis
```

---

## Migration Path: Dev → Platform → Standalone

### During Development
1. Write operators in `packages/operator_sdk/motis_operator/operators/btc_smc_long.py`
2. Test locally with `MOTIS_RUNTIME_MODE=dev`
3. Iterate quickly with IDE, Git, debugger, breakpoints

### When Deploying to Platform
1. Platform ships with **example operators** in filesystem (read-only templates)
2. On first user request, master agent can:
   - **Generate new operators** from conversation → store in DB
   - **Clone templates** → modify → store in DB as user's operator
3. All user operators live in DB (multi-user isolation, hot-patching)

### For Standalone Users
1. User installs standalone MOTIS agent: `pip install motis-agent`
2. Agent generates operators → saves to `~/.motis/operators/`
3. User can edit files directly in IDE
4. Agent loads from `~/.motis/operators/` at runtime with `MOTIS_RUNTIME_MODE=standalone`

### Export/Import Flow

**Platform → Standalone (Export)**:
```python
# User on platform: "Export my BTC strategy to a file"
operator = db.query("SELECT graph_code FROM operators WHERE operator_id = ?", id)
with open("~/.motis/operators/my_btc_strategy.py", "w") as f:
    f.write(operator["graph_code"])
```

**Standalone → Platform (Import)**:
```python
# User uploads operator file to platform
with open("my_btc_strategy.py") as f:
    graph_code = f.read()
db.execute(
    "INSERT INTO operators (user_id, name, graph_code, state) VALUES (?, ?, ?, 'draft')",
    user_id, "My BTC Strategy", graph_code
)
```

### Benefits of Single-Mode Storage

**✅ Clean Separation**
- Dev: Filesystem (Git, IDE, debugging)
- Platform: Database (multi-user, dynamic, isolated)
- Standalone: Filesystem (user control, portability)

**✅ No Hybrid Complexity**
- Only ONE storage backend active at a time
- No sync issues between filesystem and DB
- No "which is source of truth?" confusion
- Clear mental model for each mode

**✅ Smooth Migration**
- Dev operators can be "seeded" into platform DB on deployment
- Platform can ship with example operators as read-only templates
- Users can export DB operators to filesystem for standalone use
- No lock-in: operators are portable Python files

**✅ Standalone Product**
- Standalone MOTIS agent is a real product for power users
- No platform dependency
- Full control over operators and skills
- Can run on air-gapped systems

**✅ Development Velocity**
- Developers work in filesystem with full IDE support
- No need to mock database during development
- Can test operators with `pytest` and debuggers
- Version control tracks all changes

**✅ Platform Scalability**
- Database storage enables multi-tenancy
- Per-user isolation via `user_id` foreign key
- Hot-patching without filesystem writes
- Metrics and state co-located with code

---
