# Motis Agent Selective Vendoring Plan

## Goal

Use Hermes as a strong foundation for Motis without inheriting Hermes as the long-term product runtime.

We want to selectively vendor and adapt the upstream agent architecture so Motis gets:

- a mature agent loop
- strong tool-calling discipline
- sub-agent delegation
- memory orchestration
- session search
- prompt assembly and context compression

We do **not** want to inherit:

- single-user filesystem assumptions
- CLI-first architecture
- `~/.hermes` home-directory state
- generic consumer-product surfaces and branding
- large optional subsystems that do not help the Motis platform path

## Current State

The repo already has a Motis-native shell around the agent service:

- [server.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/server.py)
- [context.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/context.py)
- [loop.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/loop.py)
- [memory.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/memory.py)
- [prompts.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/prompts.py)
- [\_router.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/tools/_router.py)
- [subagent.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/tools/subagent.py)

That shell is directionally right for Motis, but today it is still much thinner than the upstream foundation:

- the live loop is OpenAI-compatible only
- tool execution is simpler than Hermes
- memory extraction is still a stub
- there is no session search yet
- prompt assembly is hand-built and missing Hermes's cached-vs-ephemeral layering
- compression is not integrated into the live loop
- provider/runtime abstraction is not ported
- there is no real procedural skill registry yet

There is also a mixed state in `motis_agent/core/`:

- [model.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/model.py) is effectively a direct upstream carry-over and still imports upstream namespaces like `tools.*`, `toolsets`, and `hermes_cli.plugins`
- [compression.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/compression.py) still imports upstream `agent.*`
- [trajectory.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/trajectory.py) still imports upstream `agent.*` and `hermes_constants`

That mixed state is the biggest architectural risk right now. If we do not resolve it early, Motis will end up with two overlapping agent stacks.

## Core Decision

Hermes should be treated as a **reference implementation plus vendored source pool**, not as a package we directly depend on from production code.

Practical rule:

- `services/agent/upstream/hermes_agent/` is the provenance boundary
- production Motis runtime code should live under `motis_agent/`
- we should avoid adding new production imports from bare upstream namespaces like `agent.*`, `tools.*`, `hermes_cli.*`, `toolsets`, or `model_tools`

Copy and adapt logic into Motis-owned modules. Do not wire the live request path directly to the upstream tree.

## What We Should Keep

### 1. Agent loop architecture

Keep the architecture and behavior of Hermes's core loop from [run_agent.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/run_agent.py):

- shared iteration budget across parent and child agents
- stable `run_conversation()` style orchestration
- explicit tool loop until completion
- interruption-aware API call structure
- preflight compression checks
- cached system prompt with ephemeral overlays
- callback surfaces for streaming/progress/status

This is the single biggest reason to use Hermes as a base.

### 2. Prompt assembly principles

Keep the architecture from [prompt_builder.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/prompt_builder.py):

- separate cached prompt state from per-call ephemeral context
- inject recalled memory as fenced context, not as fake user text
- keep tool-use enforcement guidance
- keep session-search guidance
- keep model-family-specific execution guidance where useful

Do **not** keep:

- `SOUL.md`
- `.hermes.md`
- `AGENTS.md` auto-loading for all user chats
- home-directory profile identity

Motis should build its identity and context from platform data, not filesystem lore.

### 3. Memory orchestration abstraction

Keep the abstraction pattern from:

- [memory_manager.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/memory_manager.py)
- [memory_provider.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/agent/memory_provider.py)

The right move is **not** to port Hermes's built-in filesystem memory store. The right move is:

- keep Motis's Postgres-native storage from [memory.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/memory.py)
- wrap it in a Hermes-style provider/manager abstraction
- support prefetch, turn sync, delegation hooks, and session-end hooks

That gives us the power of Hermes memory orchestration while preserving Motis's multi-user data model.

### 4. Session search capability

Keep the capability and interface shape from:

- [hermes_state.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/hermes_state.py)
- [session_search_tool.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/tools/session_search_tool.py)

But do **not** keep the SQLite runtime.

Motis should implement:

- conversation/session persistence in PostgreSQL
- search over prior turns per user
- summarized retrieval for relevant past work

This is critical for a strong agent foundation and worth porting early.

### 5. Sub-agent delegation model

Keep the delegation patterns from [delegate_tool.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/upstream/hermes_agent/tools/delegate_tool.py):

- isolated child context
- no recursive runaway delegation
- child summaries returned to parent
- shared iteration discipline
- delegation events flowing back into memory/session systems

Motis already has the beginnings of this in [subagent.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/tools/subagent.py). We should keep that Motis shape, but port the missing behaviors from Hermes.

### 6. Context compression

Keep the algorithmic ideas from Hermes compression:

- rough preflight token estimation
- middle-turn summarization
- tool-result pruning
- iterative compaction

This should become a Motis-owned service module and be integrated into the live loop.

### 7. Provider/runtime support

Keep the upstream provider/runtime concepts where they improve flexibility:

- model family detection
- API mode switching
- retry utilities
- auxiliary model calls
- context length lookup

This is useful because Motis is BYOM and will eventually want stronger model portability.

## What We Should Adapt Heavily

### 1. Tool registry

Hermes uses a process-global tool discovery model driven by imports and toolsets.

Motis should keep the **concept** of a registry, but adapt it to:

- per-request `UserContext`
- platform-controlled tool availability
- strict separation between native tools and Motis MCP tools
- explicit schemas over magic discovery

Today [\_registry.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/tools/_registry.py) and [\_router.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/tools/_router.py) are closer to the right long-term shape than upstream `model_tools.py`.

### 2. Skills system

This needs a naming decision before we port more.

Motis PRD already uses **Skill** to mean lightweight callable capabilities like `fetch_ohlcv`, `calc_rsi`, and `detect_bos`.

Hermes uses **Skill** to mean a procedural markdown workflow stored in `SKILL.md`.

Those are two different abstractions with the same name.

Recommendation:

- keep Motis PRD meaning of `Skill` for callable finance/operator capabilities
- port Hermes procedural skill system later, but rename it in Motis to something like `playbooks`, `workflows`, or `operator_playbooks`

Do not import Hermes procedural skills into Motis under the same `skills/` concept or the architecture will stay muddy forever.

### 3. Session store implementation

We should adapt the interfaces from `hermes_state.py`, not the persistence backend.

Motis session storage should be:

- PostgreSQL
- scoped by `user_id` and `conversation_id`
- compatible with SSE/web service request boundaries
- able to support later analytics, operator linking, and marketplace/audit needs

### 4. MCP integration

Hermes supports dynamic arbitrary MCP discovery. Motis does not need that whole system right now.

Motis should keep:

- a clean MCP client boundary
- structured tool invocation
- auth around the MCP service

Motis should leave out:

- arbitrary external MCP server discovery
- oauth-heavy MCP runtime complexity
- generalized MCP utility surface until there is a real product need

## What We Should Leave Out

These are not foundation-critical for Motis right now:

- `cli.py`
- `hermes_cli/`
- `gateway/`
- `acp_adapter/`
- `cron/`
- `environments/`
- `rl_cli.py`
- voice, TTS, transcription, Home Assistant, SMS, Discord/Telegram delivery plumbing
- install/update scripts
- profile system and `HERMES_HOME`
- bundled community skill hub machinery
- browser automation stack

These may be useful later, but they are not part of the shortest path to a strong Motis agent platform.

## Recommended Target Shape

Motis should keep the service shell it already has:

- `server.py` remains the FastAPI/SSE boundary
- `context.py` remains the multi-user context resolution layer
- `tools/` remains where Motis-native and MCP-bound tools live

Then gradually strengthen `motis_agent/core/` into the real foundation:

```text
motis_agent/core/
├── agent_runtime.py         # ported/adapted from run_agent.py
├── prompts.py               # ported/adapted prompt builder
├── memory_manager.py        # Hermes-style manager
├── memory_provider.py       # provider interface
├── session_store.py         # Postgres session/search interface
├── compression.py           # Motis-owned context compressor
├── provider_runtime.py      # API mode / provider routing / metadata
├── auxiliary_client.py      # side-model calls
├── retry_utils.py           # provider retry helpers
└── playbooks.py             # later: procedural skills renamed for Motis
```

This keeps the outer Motis API stable while swapping in stronger internals.

## Porting Order

### Phase 1: Clean the boundary

Before porting more code:

- stop adding runtime imports from upstream namespaces into `motis_agent/`
- treat [model.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/model.py), [compression.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/compression.py), and [trajectory.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/trajectory.py) as quarantine candidates
- decide which of those will be fully adapted vs removed from the live path

### Phase 2: Port provider/runtime utilities

Port and adapt the smaller, high-value upstream modules first:

- retry utilities
- auxiliary client
- model metadata/context length
- error classification

This is low-risk and immediately strengthens the live loop.

### Phase 3: Add session persistence and search

Implement a Motis-native `SessionStore` with:

- conversation/session writes on every turn
- tool-call persistence
- search over prior sessions
- session summary retrieval

Then wire `session_search` into the tool router.

### Phase 4: Port memory orchestration

Introduce:

- `MemoryProvider` interface
- `MemoryManager`
- `PostgresMemoryProvider` backed by current [memory.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/memory.py)

This gives us Hermes memory behavior without losing Motis's multi-user design.

### Phase 5: Replace the thin custom loop with a Motis-owned port of AIAgent

Port the useful orchestration semantics from `run_agent.py` into a new Motis runtime:

- async-first
- SSE-friendly
- no CLI assumptions
- no filesystem assumptions
- `UserContext` aware
- Motis router aware

This should replace, not stack on top of, the current thin loop.

### Phase 6: Strengthen delegation

Once the new runtime exists:

- make subagents consume shared iteration budgets
- persist child sessions
- route delegation summaries into memory/session systems
- carry better progress events back to the parent stream

### Phase 7: Introduce procedural playbooks

After the core runtime is stable:

- port Hermes procedural skill architecture
- rename it in Motis
- keep it clearly separate from callable finance/operator skills

## Current Gaps To Fix Soon

These are the highest-signal gaps in the current tree:

### 1. Missing `core.skills`

[context.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/context.py) references `motis_agent.core.skills.SkillRegistry`, but that module does not exist yet.

### 2. Thin loop vs orphaned upstream modules

The live request path uses [loop.py](/Users/haokaiqin/Desktop/RR%20Ratio/Motis/services/agent/motis_agent/core/loop.py), but several stronger upstream-derived modules are sitting nearby without being cleanly integrated.

That should be resolved deliberately, not organically.

### 3. No session search yet

Hermes gets a lot of leverage from durable searchable transcripts. Motis should port this early.

### 4. Memory extraction is still stubbed

The current loop calls `_maybe_save_memory()` but does not actually extract or persist memory-worthy outputs.

### 5. Skills naming collision

This is an architecture issue, not a wording nit. We should resolve it before porting Hermes procedural skills.

## Recommendation

Use Hermes as the **orchestration reference** and Motis as the **runtime owner**.

That means:

- keep Motis-native `UserContext`, Postgres memory, operator registry, and MCP trust boundary
- port Hermes loop/prompt/memory/session abstractions into Motis-owned modules
- leave out Hermes product surfaces and home-directory runtime model
- rename Hermes procedural skills before bringing them over

This gives Motis the strongest part of Hermes: the foundation.

It also keeps us on the path to the long-term goal: a standalone Motis agent that no longer feels or behaves like a fork.
