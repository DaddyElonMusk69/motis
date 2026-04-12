# Motis Runtime Alignment

## Purpose

This note defines the intended standalone-runtime architecture while Motis is
still living inside the current repo layout.

The goal is to avoid "Hermes plus Motis patches" and keep one clear runtime
shape:

- Motis persists core runtime state in a database.
- Motis reaches the network through MCP boundaries.
- Operators stay filesystem-backed for now.

## Current Runtime Boundaries

### 1. Persistence is DB-shaped

Core conversation and memory persistence is already DB-backed in the standalone
runtime:

- `services/motis_agent/motis_state.py`
- `services/motis_agent/motis_storage.py`
- Read-only consumers such as `motis status` and `motis sessions list` should
  query the same SQLite store without initializing schema or attempting writes.

This local DB layer is the standalone bridge toward the platform schema in:

- `services/platform/motis_platform/db/models.py`

That means Motis should not add new JSONL or ad-hoc file persistence for
conversation history, memory, or similar runtime state.

Operational note:

- `~/.motis/state.db` is the durable conversation and memory store.
- `~/.motis/sessions/` is not a second transcript store; it is reserved for
  gateway routing metadata such as `sessions.json`.
- Full JSON session snapshots, when needed for debugging, are opt-in only via
  `MOTIS_DEBUG_SESSION_JSON=1`.

### 2. Networking is MCP-first

Web and finance data access should route through the Motis Data MCP boundary:

- Agent-side callers:
  - `services/motis_agent/tools/web_tools.py`
  - `services/motis_agent/tools/motis_finance_tool.py`
- MCP service:
  - `services/mcp/motis_data_mcp/`

Standalone runtime configuration should use:

- `DATA_MCP_URL` as the preferred HTTP endpoint
- `MCP_URL` only as a compatibility alias

The agent runtime should not silently fall back to in-process provider calls.

### 3. Operators remain filesystem-backed for now

Operators are intentionally not part of the DB migration yet.

Current operator boundary:

- Bundled operators: `services/motis_agent/operators/`
- User/runtime operators: `~/.motis/operators`
- Registry: `services/motis_agent/agent/operator_registry.py`

This is intentional until the platform phase starts.

## Intentional Local Files

These local files/directories are currently acceptable operational state, not a
reason to reintroduce a second persistence architecture:

- `~/.motis/config.yaml`
- `~/.motis/.env`
- `~/.motis/auth.json`
- `~/.motis/operators/`
- `~/.motis/sessions/sessions.json` for gateway route/session-key mapping
- gateway pairing files
- cron job definitions and output files
- sticker/media caches

They are control-plane/config/cache artifacts, not the primary memory and
conversation store.

## Residual Hermes-Era Cleanup Still Pending

These areas still need follow-up cleanup so the runtime matches Motis more
cleanly:

- `motis_state.py` still carries legacy compatibility migration helpers for old
  Hermes `sessions` / `messages` tables.
- `services/motis_agent/tools/web_tools.py` still contains some old provider
  helper code that is no longer part of the active runtime path and should be
  deleted in a follow-up cleanup pass.
- Some gateway operational data is still file-backed:
  - pairing JSON
  - sticker cache JSON
  - cron job JSON/output files
- Hermes naming still exists in many symbols, comments, and docs even where the
  runtime behavior is now Motis-shaped.

## Non-Goals Right Now

These are explicitly not part of the current cleanup pass:

- Moving operators into the platform DB
- Replacing the standalone local DB with the platform API/DB service
- Broad search-and-replace renaming without first resolving architecture

## Practical Rule

When adding or refactoring runtime features:

- If it needs network access, route it through MCP.
- If it needs durable agent state, put it in the DB-shaped persistence layer.
- If it is an operator definition, keep it under `motis/operators` for now.
