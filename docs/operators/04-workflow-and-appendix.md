
## Summary: The Build Flow

```
User intent (natural language)
        │
        ▼
Master agent (loads operator-builder SKILL.md)
        │
        ├── 1. Decompose strategy into steps
        ├── 2. Classify each step (DATA/COMPUTE/REASON/GUARD/EXECUTE)
        ├── 3. Show decomposition to user for approval
        ├── 4. Generate Python module (STATE + MANIFEST + build_graph)
        ├── 5. Run Quality Gate (10-point checklist)
        │      ├── Pass → store as DRAFT
        │      └── Fail → fix code, re-run gate
        ├── 6. operator_create() → store in DB as PAPER
        ├── 7. operator_invoke() → run backtest
        ├── 8. Present backtest results
        │      ├── Good → ask user to confirm for LIVE
        │      └── Bad → iterate (adjust params, prompts, logic)
        │
        ▼
User confirms → operator goes LIVE
        │
        ▼
Operator runs autonomously on schedule
Master agent monitors via operator_status()
```

> [!IMPORTANT]
> **Next steps (implementation order):**
> 1. **Database schema** — Create `operators` and `skills` tables for platform mode
> 2. **Operator registry** — Implement mode-based loading (dev/platform/standalone)
> 3. **Operator-builder skill** — Write `skills/operator-builder/SKILL.md` that teaches the agent the contract
> 4. **SDK implementation** — Implement `motis_operator.sdk` with mode-aware routing
> 5. **Quality Gate** — Implement `motis_operator.validation` (AST analysis of generated code)
> 6. **MCP tools** — Add operator management tools to MOTIS Operator MCP server
> 7. **Standalone runner** — Implement `python -m motis_operator.runner` for local execution
> 8. **Example operators** — Create 3-5 example operators in `packages/operator_sdk/motis_operator/operators/`

---

## Appendix: Database Schema

### Operators Table (Platform Mode)

```sql
CREATE TABLE operators (
    operator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    name TEXT NOT NULL,
    description TEXT,
    
    -- The complete Python module
    graph_code TEXT NOT NULL,
    
    -- Parsed MANIFEST for fast queries (denormalized)
    manifest JSONB NOT NULL,
    
    -- State machine
    state TEXT NOT NULL CHECK (state IN ('draft', 'validating', 'paper', 'live', 'paused', 'archived')),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_run_at TIMESTAMPTZ,
    
    -- Performance metrics (updated after each run)
    total_pnl_usd NUMERIC(20, 8),
    total_pnl_pct NUMERIC(10, 4),
    sharpe_ratio NUMERIC(10, 4),
    max_drawdown_pct NUMERIC(10, 4),
    win_rate NUMERIC(10, 4),
    total_trades INTEGER DEFAULT 0,
    
    -- Constraints
    UNIQUE(user_id, name)
);

CREATE INDEX idx_operators_user_state ON operators(user_id, state);
CREATE INDEX idx_operators_last_run ON operators(last_run_at DESC);
```

### Skills Table (Platform Mode)

```sql
CREATE TABLE skills (
    skill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),  -- NULL = platform skill
    name TEXT NOT NULL,
    category TEXT NOT NULL,  -- data, analysis, research, reporting
    
    -- SKILL.md content
    content TEXT NOT NULL,
    
    -- Optional signal engine code
    signal_engine_code TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(user_id, name),
    CHECK (user_id IS NOT NULL OR name NOT LIKE 'user_%')  -- Platform skills can't start with user_
);

CREATE INDEX idx_skills_user_category ON skills(user_id, category);
CREATE INDEX idx_skills_platform ON skills(user_id) WHERE user_id IS NULL;
```

### Operator Run Logs Table

```sql
CREATE TABLE operator_run_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operators(operator_id) ON DELETE CASCADE,
    run_id UUID NOT NULL,  -- Groups logs from same tick
    
    -- Log entry
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    node_name TEXT NOT NULL,
    message TEXT NOT NULL,
    data JSONB,  -- Structured data from log_event()
    
    -- For querying
    level TEXT DEFAULT 'info' CHECK (level IN ('debug', 'info', 'warning', 'error'))
);

CREATE INDEX idx_operator_run_logs_operator ON operator_run_logs(operator_id, timestamp DESC);
CREATE INDEX idx_operator_run_logs_run ON operator_run_logs(run_id, timestamp);
```
