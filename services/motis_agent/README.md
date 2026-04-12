# Motis Agent

Motis Agent is the standalone agent runtime for Motis: a trading-focused, operator-aware AI agent that can research markets, use structured finance tools, manage durable workflow operators, and run through a local CLI.

This folder is the agent itself, not the full Motis platform. The broader platform vision includes separate MCP services for market data, web/network access, execution, backtesting, and deployment. The agent is the conversational control plane that sits on top of that stack.

## Status

This repo is under active development.

What is already here:

- standalone CLI with setup wizard, streaming output, memory, session recall, and tool calling
- OpenAI-compatible model support with custom `base_url`, `api_key`, and model selection
- dynamic skill discovery from folder-based `SKILL.md` files
- dynamic operator discovery from folder-based `OPERATOR.md` files
- built-in finance tools for structured market and macro data
- sub-agent delegation and multi-model reasoning utilities
- a separate MCP boundary for external data and execution

What is still evolving:

- the full Motis platform experience around the agent
- the dedicated MCP services and backend integrations
- operator execution depth, backtesting flows, and platform orchestration

## What Motis Is For

Motis is designed for trading and investment workflows, not generic chat.

The agent is meant to help with tasks like:

- market research
- structured data retrieval
- strategy ideation and refinement
- operator creation and operator lifecycle management
- portfolio and risk review
- multi-step analysis using skills, tools, and delegated sub-agents

The runtime prompt is finance- and operator-aware. It pushes the model to prefer structured tools over vague narrative answers, route network/data access through Motis-owned interfaces, and treat operators as durable workflow assets rather than one-off notes or scripts.

## Core Concepts

### Skills

Skills are folder-based playbooks discovered from `skills/**/SKILL.md`.

They are lightweight capability modules the agent can load on demand. In practice, skills are where reusable domain workflows live: finance analysis methods, research playbooks, coding helpers, document readers, and similar procedural knowledge.

### Operators

Operators are durable workflow artifacts discovered from `operators/**/OPERATOR.md` plus `operator.py`.

They are not just prompts. An operator is a solidified workflow with explicit scope, graph shape, variables, and lifecycle. Motis can list operators, read their discovery cards, load the full operator description, invoke them, inspect status, pause them, archive them, and export them.

The current operator contract is documented in [`../../docs/operators/02-contract-and-validation.md`](../../docs/operators/02-contract-and-validation.md).

### MCP Boundary

Motis is being built around a separate MCP layer for external connectivity.

That means:

- market data should come through Motis data tools or data MCP
- execution should go through a guarded execution boundary
- operators and sub-agents should use logical Motis tools instead of raw ad hoc provider calls when a Motis interface exists

This keeps the agent layer clean and makes the networking/data plane separable from the conversational runtime.

## Current Runtime Capabilities

Depending on configuration, Motis can expose tools such as:

- `data.resolve_symbol`
- `data.ohlcv`
- `data.ticker`
- `data.orderbook`
- `data.funding_rate`
- `data.open_interest`
- `macro.get_series`
- `equity.get_fundamentals`
- `equity.get_earnings_calendar`
- `flows.get_connect`
- `china.get_moneyflow`
- `smc.structure`
- `web_search`
- `read_url`
- `web_fetch`
- `delegate_task`
- `mixture_of_agents`
- operator lifecycle tools
- memory and session recall tools

Exactly which tools are active depends on your local configuration and which backends are available.

## Quick Start

Run Motis directly from this folder:

```bash
cd services/motis_agent
./setup-motis.sh
./motis setup
./motis
```

If you prefer make targets:

```bash
make bootstrap
make setup
make chat
```

The local launcher is designed to work from inside `services/motis_agent` and will use the local environment there.

## Configuration

Motis reads runtime settings from `.env`.

Start from the included template:

```bash
cp .env.example .env
```

Important settings:

- `MOTIS_MODEL`: default model name
- `MOTIS_BASE_URL`: OpenAI-compatible provider URL
- `MOTIS_API_KEY`: model provider key
- `DATA_MCP_URL`: URL for the Motis data MCP
- `AGENT_MCP_SECRET`: shared secret for trusted MCP access
- `BRAVE_API_KEY` / `TAVILY_API_KEY`: optional web research backends
- `LOCAL_STATE_DIR`: local standalone state directory, default `.motis`
- `RUNTIME_MODE`: standalone vs platform-oriented runtime mode

Example for an OpenAI-compatible provider:

```env
MOTIS_MODEL=gpt-5.3-codex
MOTIS_BASE_URL=https://api.openai.com/v1
MOTIS_API_KEY=your_key_here
```

If you are using a custom provider, set `MOTIS_BASE_URL` and `MOTIS_API_KEY` accordingly, then run:

```bash
./motis setup
```

## Common Commands

```bash
./motis                 # launch the interactive CLI
./motis setup           # run the setup wizard
./motis model           # switch or configure model/provider
./motis tools           # inspect tool configuration
./motis doctor          # diagnose setup issues
./motis --help          # show CLI help
```

There is also a direct agent entrypoint:

```bash
motis-agent
```

and a packaged CLI entrypoint when installed into an environment:

```bash
motis
```

## Local State

In standalone mode, Motis keeps its working state locally.

Common local state includes:

- `.env` for runtime configuration
- `.motis/` for local state
- local sessions, memories, operators, and related runtime artifacts

The standalone defaults are intentionally local-first so you can iterate quickly during development.

## Development Workflow

From inside `services/motis_agent`:

```bash
make bootstrap
make test
make build
```

Or install editable dependencies manually:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -e ".[dev]"
```

Then run:

```bash
pytest -c pyproject.toml tests -q
```

## Repository Layout

Important paths in this folder:

- `run_agent.py` - main agent loop and tool-calling runtime
- `motis_cli/` - CLI commands, setup, config, and doctor flows
- `agent/` - prompt, memory, operator, and runtime support code
- `tools/` - native tool implementations
- `skills/` - dynamically discovered skill library
- `operators/` - dynamically discovered operators
- `tests/` - agent and runtime tests
- `.env.example` - local configuration template
- `cli-config.yaml.example` - example CLI config

Useful repo-level docs:

- [`../../docs/motis_prd.md`](../../docs/motis_prd.md)
- [`../../docs/operators/README.md`](../../docs/operators/README.md)
- [`../../docs/architecture/motis-runtime-alignment.md`](../../docs/architecture/motis-runtime-alignment.md)
- [`../../docs/mcp_quick_reference.md`](../../docs/mcp_quick_reference.md)

## Notes

- This agent is trading-focused and should not be treated as a generic assistant README with every historical gateway/platform feature documented.
- Real-time finance answers are only as good as the configured data and web backends.
- Live execution should remain behind guarded MCP services rather than direct raw agent calls.
- This codebase is being shaped toward a native Motis architecture. The goal is a clean Motis runtime, not a rebranded general-purpose agent.

## License

Proprietary demo software. All rights reserved. See [`LICENSE`](LICENSE).
