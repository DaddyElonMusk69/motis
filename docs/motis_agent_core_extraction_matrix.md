# Motis Agent Core Extraction Matrix

## Purpose

This document turns the selective-vendoring strategy into an actual extraction plan.

It answers four questions for each major upstream source file:

1. what Motis should keep
2. what Motis should adapt
3. what Motis should leave out
4. which Motis-owned files should receive the extracted logic

## Ground Rules

- Upstream source of truth lives under [services/agent/upstream/hermes_agent](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent)
- Production runtime code lives under [services/agent/motis_agent](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent)
- Quarantined carry-overs live under [services/agent/motis_agent/_upstream_quarantine](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/_upstream_quarantine)
- Do not port giant files wholesale. Extract behaviors into smaller Motis-owned modules.

## Current Phase 1 Cleanup

Completed in this repo state:

- Added a real [skills.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/skills.py) so the runtime no longer points at a missing module
- Switched [loop.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/loop.py) to depend on `SkillRegistry` instead of importing finance tool definitions directly
- Quarantined the upstream-derived non-runtime carry-overs in [\_upstream_quarantine](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/_upstream_quarantine)

## Current Phase 2 Foundation

Completed in this repo state:

- Added a Motis-owned async memory abstraction:
  - [memory_provider.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/memory_provider.py)
  - [memory_manager.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/memory_manager.py)
  - [memory_providers/postgres.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/memory_providers/postgres.py)
- Wired the live agent runtime to use `MemoryManager` for:
  - provider-owned memory tool definitions
  - per-turn memory prefetch
  - memory tool routing
  - delegation hook surfaces
- Kept [memory.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/memory.py) as the storage implementation and wrapped it instead of copying upstream storage behavior
- Removed the operator registry's hidden dependency on `motis_platform` so the agent service can construct [UserContext](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/context.py) without importing the full platform package

## Extraction Matrix

### 1. `run_agent.py`

Source:
- [run_agent.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/run_agent.py#L439)

Keep:
- `AIAgent` conversation loop structure
- shared iteration budget
- repeated tool-call loop until final answer
- preflight compression checks
- cached system prompt reuse
- callback/event surfaces
- tool-call ordering and batching discipline
- delegation integration points

Adapt heavily:
- make the runtime async-first and SSE-first
- replace filesystem/session assumptions with `UserContext` and Postgres session store
- replace global tool dispatch with Motis router/registry
- replace CLI/gateway status printing with stream events
- replace home-directory memory/session setup with service-owned initialization

Leave out:
- CLI rendering, spinners, kawaii display
- gateway/platform glue
- plugin hook system in first pass
- todo tool state hydration in first pass
- ACP and profile behavior
- direct filesystem memory writes

Target Motis-owned files:
- `services/agent/motis_agent/core/agent_runtime.py`
- `services/agent/motis_agent/core/budget.py`
- `services/agent/motis_agent/core/provider_runtime.py`
- `services/agent/motis_agent/core/runtime_events.py`

Recommended extraction slices:
- Slice A: `IterationBudget` and max-turn enforcement
- Slice B: model call orchestration and API mode selection
- Slice C: tool-call loop and result reinsertion
- Slice D: session-store writes and replay loading
- Slice E: compression integration
- Slice F: delegation integration

Dependencies to port before or alongside:
- [retry_utils.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/retry_utils.py)
- [auxiliary_client.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/auxiliary_client.py)
- [model_metadata.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/model_metadata.py)
- [error_classifier.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/error_classifier.py)
- [anthropic_adapter.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/anthropic_adapter.py)

### 2. `prompt_builder.py`

Source:
- [prompt_builder.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/prompt_builder.py#L134)

Keep:
- cached prompt vs ephemeral prompt layering
- tool-use enforcement guidance
- model-family-specific execution guidance
- memory/session-search guidance
- compact skill-index/prompt-block composition ideas

Adapt heavily:
- use Motis identity and platform instructions
- inject operator context and Motis tool guidance
- use DB-backed memory/session context instead of files
- derive callable skill catalogue from Motis registries

Leave out:
- `SOUL.md`
- `.hermes.md`
- `HERMES_HOME`
- automatic `AGENTS.md`/`CLAUDE.md` injection for end-user chats
- Nous subscription and other product-specific prompt sections

Target Motis-owned files:
- `services/agent/motis_agent/core/prompts.py`
- `services/agent/motis_agent/core/prompt_layers.py`
- `services/agent/motis_agent/core/model_guidance.py`

Recommended extraction slices:
- Slice A: tool-use enforcement blocks
- Slice B: model-family-specific guidance blocks
- Slice C: prompt layering API
- Slice D: Motis memory/operator/session overlays

Dependencies to port before or alongside:
- [skill_utils.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/skill_utils.py)

Note:
- Do not port the upstream procedural `SKILL.md` terminology directly into Motis prompting. If we bring that system over later, rename it.

### 3. `memory_manager.py` and `memory_provider.py`

Sources:
- [memory_manager.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/memory_manager.py#L72)
- [memory_provider.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/memory_provider.py)

Keep:
- provider abstraction
- orchestration over one or more providers
- prefetch API
- tool-routing API for provider-owned tools
- lifecycle hooks: turn start, session end, pre-compress, delegation
- fenced memory-context injection helpers

Adapt heavily:
- use async interfaces
- make Postgres-backed memory the built-in Motis provider
- scope everything by `user_id` and `conversation_id`
- integrate with SSE/web request lifecycle

Leave out:
- built-in filesystem provider behavior
- `MEMORY.md` / `USER.md`
- plugin-discovered external providers in first pass
- profile/home-directory setup

Target Motis-owned files:
- `services/agent/motis_agent/core/memory_provider.py`
- `services/agent/motis_agent/core/memory_manager.py`
- `services/agent/motis_agent/core/memory_providers/postgres.py`

Recommended extraction slices:
- Slice A: `MemoryProvider` interface
- Slice B: `MemoryManager` orchestration
- Slice C: fenced context helpers
- Slice D: Postgres provider wrapping current [memory.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/memory.py)

Important rule:
- Keep [memory.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/memory.py) as the storage implementation; do not regress to upstream storage patterns.

### 4. `hermes_state.py`

Source:
- [hermes_state.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/hermes_state.py#L115)

Keep:
- session/message schema concepts
- full transcript persistence
- replay into conversation format
- search capability over prior messages
- title/lineage concepts only if they help Motis UX later

Adapt heavily:
- move from SQLite FTS5 to PostgreSQL
- scope by `user_id` and `conversation_id`
- align with Motis platform schema and API
- separate raw storage from summarization/search services

Leave out:
- SQLite WAL tuning and lock-retry logic
- filesystem/log duplication
- CLI/gateway source tagging complexity in first pass

Target Motis-owned files:
- `services/agent/motis_agent/core/session_store.py`
- `services/agent/motis_agent/core/session_search.py`
- `services/agent/motis_agent/core/session_models.py`

Recommended extraction slices:
- Slice A: session/message write API
- Slice B: conversation replay API
- Slice C: transcript search API
- Slice D: summarized search results

Dependencies to port before or alongside:
- [session_search_tool.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/tools/session_search_tool.py)
- summarization helpers from [auxiliary_client.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/auxiliary_client.py)

## Immediate Build Order

Recommended order for the next coding slices:

1. `memory_provider.py`
2. `memory_manager.py`
3. `session_store.py`
4. `session_search.py`
5. `provider_runtime.py`
6. `agent_runtime.py`
7. prompt-layer refactor in `prompts.py`
8. delegation/runtime integration cleanup

Why this order:

- memory and session abstractions are foundational and unblock the loop
- provider/runtime utilities are smaller than the full loop port
- the loop port gets much easier once storage and provider interfaces exist

## Explicit Non-Goals For The Next Slice

Do not tackle these in the next extraction step:

- messaging gateway
- CLI/TUI behavior
- cron jobs
- RL / trajectory tooling
- browser tool stack
- procedural markdown skills

Those are optional surfaces, not core Motis runtime blockers.
