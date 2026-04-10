# Upstream Agent Fork Boundary

This directory is the Motis fork boundary for the upstream agent platform.

## Source

- Upstream repo: `https://github.com/NousResearch/hermes-agent`
- Pinned commit: `b87d00288d68b7e63df86eb0f11134e8f1304ec9`
- License: MIT

The imported source snapshot lives under `services/agent/upstream/hermes_agent/`.

## Why This Exists

Motis wants the upstream architecture, not the upstream product identity.

We are forking the agent platform because it already has strong building blocks:

- A mature agent loop
- Prompt assembly and context compression
- Provider/runtime abstraction
- Tool registry and MCP integration
- Session persistence and search
- Messaging gateway patterns

We do **not** want to keep the upstream product naming spread throughout first-party Motis code.

## Naming Rule

Keep upstream naming isolated to this `upstream/` boundary and attribution docs.

For new Motis-first code:

- Prefer `motis_agent` naming over upstream product names
- Refer to the imported code as the `upstream agent platform` or `forked agent foundation`
- Avoid introducing new first-party imports, modules, comments, or docs that hard-code the upstream product name unless they are explicitly about provenance

## What Motis Will Keep

- Core conversation loop patterns from `run_agent.py`
- Prompt assembly concepts from `agent/prompt_builder.py`
- Context compression and caching strategy
- Tool registry and MCP client architecture
- Session persistence/search model
- Gateway and multi-surface delivery patterns where useful

## What Motis Will Replace

- Single-user home-directory state with DB-backed `UserContext`
- CLI-first assumptions with web/SSE-first service boundaries
- Generic bundled skills with Motis-native finance skills and operator tools
- Upstream branding, personalities, install flows, and end-user product surfaces
- Local/session filesystem persistence with multi-user platform storage

## Recommended Adaptation Order

1. Extract the upstream agent loop into `motis_agent/core/`
2. Swap filesystem/session assumptions for DB + Redis + `UserContext`
3. Preserve provider/runtime and tool abstractions where they still fit
4. Replace prompt identity and context-file behavior with Motis defaults
5. Re-introduce messaging surfaces only after the web platform path is solid

## Re-importing

Use:

```bash
./scripts/import_hermes_upstream.sh
```

If we refresh the fork later, we should update:

- `services/agent/upstream/HERMES_UPSTREAM_COMMIT`
- this file's pinned commit
- any Motis adaptation notes that depend on specific upstream behavior
