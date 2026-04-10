"""
Motis Tool Definition Registry
================================
Maps tool names to their OpenAI function-calling schema definitions
and provides get_tool_definitions() used by MotisAgentLoop.

Adapted from Hermes tools/registry.py + toolsets.py.
Key difference: no process-global mutable state.
All definitions are module-level constants (immutable after import).
"""

from __future__ import annotations

# ── Tool schema definitions ───────────────────────────────────────────────────

_TOOL_DEFINITIONS: dict[str, dict] = {

    # ── Memory ────────────────────────────────────────────────────────────────
    "memory_add": {
        "type": "function",
        "function": {
            "name": "memory_add",
            "description": (
                "Save a piece of information to long-term memory. Use this to remember "
                "user preferences, strategy decisions, key facts, or anything the user "
                "wants to be recalled in future conversations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The information to remember. Be specific and concise.",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["general", "strategy", "risk_pref", "agent_insight"],
                        "description": "Category of the memory.",
                        "default": "general",
                    },
                    "importance": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Importance score 1-10. Use 8-10 for critical preferences.",
                        "default": 5,
                    },
                },
                "required": ["content"],
            },
        },
    },

    "memory_search": {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": (
                "Search long-term memory for relevant information using full-text search. "
                "Call this at the start of a conversation about a topic the user has "
                "discussed before."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant memories.",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 8,
                        "description": "Max results to return.",
                    },
                },
                "required": ["query"],
            },
        },
    },

    "memory_recall": {
        "type": "function",
        "function": {
            "name": "memory_recall",
            "description": "Retrieve the most recent memories without a search query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20},
                },
            },
        },
    },

    # ── Web ───────────────────────────────────────────────────────────────────
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for recent information. Use for: market news, "
                "earnings releases, macro events, regulatory news, company information, "
                "or any real-time information not in training data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                },
                "required": ["query"],
            },
        },
    },

    "web_fetch": {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": (
                "Fetch and read the content of a specific URL. Use for: reading "
                "financial reports, SEC filings, research papers, or any specific page."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch."},
                },
                "required": ["url"],
            },
        },
    },

    # ── Terminal ──────────────────────────────────────────────────────────────
    "terminal": {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": (
                "Execute Python code in a sandboxed environment. Use for: "
                "ad-hoc data analysis, custom calculations, quick backtesting scripts, "
                "data transformations, or any computation requiring code. "
                "No network access from within the sandbox. 30-second timeout."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Python code to execute.",
                    },
                },
                "required": ["command"],
            },
        },
    },

    # ── Delegation ────────────────────────────────────────────────────────────
    "delegate_task": {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": (
                "Spawn 1-3 parallel sub-agents to work on independent tasks simultaneously. "
                "Use when you need to do multiple things at once that don't depend on each other. "
                "DO NOT use for research/analysis — use operator_invoke with a ResearchOperator instead. "
                "Example: fetch macro data AND run technical analysis AND check funding rates in parallel."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "Single task goal (use this for single-task delegation).",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional additional context for the sub-agent.",
                    },
                    "tasks": {
                        "type": "array",
                        "description": "Multiple tasks for parallel delegation (batch mode).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "goal": {"type": "string"},
                                "context": {"type": "string"},
                            },
                            "required": ["goal"],
                        },
                        "maxItems": 3,
                    },
                    "max_turns": {
                        "type": "integer",
                        "default": 20,
                        "description": "Max turns per sub-agent.",
                    },
                },
            },
        },
    },

    "mixture_of_agents": {
        "type": "function",
        "function": {
            "name": "mixture_of_agents",
            "description": (
                "Route a hard analytical problem through multiple frontier LLMs and synthesize "
                "the best answer. Makes multiple API calls — use sparingly for genuinely difficult "
                "problems. Best for: complex mathematical analysis, algorithm design, problems "
                "where a single model might miss important considerations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_prompt": {
                        "type": "string",
                        "description": "The complex problem to solve.",
                    },
                },
                "required": ["user_prompt"],
            },
        },
    },

    # ── Operator tools ────────────────────────────────────────────────────────
    "operator_create": {
        "type": "function",
        "function": {
            "name": "operator_create",
            "description": (
                "Create a new operator (trading strategy, research schedule, or backtest). "
                "Returns the operator ID. The operator starts in 'draft' state."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["live_trade", "paper_trade", "backtest", "research"],
                    },
                    "spec": {
                        "type": "object",
                        "description": "Operator specification (strategy params, schedule, risk limits).",
                    },
                },
                "required": ["name", "type", "spec"],
            },
        },
    },

    "operator_list": {
        "type": "function",
        "function": {
            "name": "operator_list",
            "description": "List all operators for the current user with their state and recent metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state_filter": {
                        "type": "string",
                        "enum": ["all", "live", "paper", "paused", "draft", "complete"],
                        "default": "all",
                    },
                },
            },
        },
    },

    "operator_invoke": {
        "type": "function",
        "function": {
            "name": "operator_invoke",
            "description": (
                "Run an operator synchronously (for BacktestOperator and ResearchOperator). "
                "Returns when complete. For live/paper operators, use operator_create + monitor sidebar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operator_id": {"type": "string", "description": "Operator UUID."},
                    "input": {
                        "type": "object",
                        "description": "Optional runtime input overrides.",
                    },
                },
                "required": ["operator_id"],
            },
        },
    },

    "operator_status": {
        "type": "function",
        "function": {
            "name": "operator_status",
            "description": "Get the current status, state, and recent log of a running operator.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operator_id": {"type": "string"},
                },
                "required": ["operator_id"],
            },
        },
    },

    "operator_pause": {
        "type": "function",
        "function": {
            "name": "operator_pause",
            "description": "Pause a live or paper trading operator.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operator_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["operator_id"],
            },
        },
    },

    "operator_archive": {
        "type": "function",
        "function": {
            "name": "operator_archive",
            "description": "Archive (deactivate) an operator.",
            "parameters": {
                "type": "object",
                "properties": {"operator_id": {"type": "string"}},
                "required": ["operator_id"],
            },
        },
    },

    # ── Execution tools (only included when user has connected exchange) ───────
    "execute_paper_trade": {
        "type": "function",
        "function": {
            "name": "execute_paper_trade",
            "description": "Execute a simulated paper trade order through the risk-guarded MCP layer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "size": {"type": "number"},
                    "order_type": {"type": "string", "enum": ["market", "limit"]},
                    "price": {"type": "number"},
                    "operator_id": {"type": "string"},
                },
                "required": ["symbol", "side", "size", "order_type"],
            },
        },
    },

    "execute_live_trade": {
        "type": "function",
        "function": {
            "name": "execute_live_trade",
            "description": (
                "Execute a live trade order. ALWAYS requires explicit user confirmation "
                "before calling. Risk guard enforced at the MCP layer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "size": {"type": "number"},
                    "order_type": {"type": "string", "enum": ["market", "limit"]},
                    "price": {"type": "number"},
                    "exchange": {"type": "string"},
                    "operator_id": {"type": "string"},
                },
                "required": ["symbol", "side", "size", "order_type", "exchange"],
            },
        },
    },

    "get_positions": {
        "type": "function",
        "function": {
            "name": "get_positions",
            "description": "Get current open positions and account balance from the connected exchange.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exchange": {"type": "string", "description": "Exchange name (optional, defaults to primary)."},
                },
            },
        },
    },
}


def get_tool_definitions(names: list[str]) -> list[dict]:
    """
    Return OpenAI tool schema dicts for the given tool names.
    Unknown names are silently skipped (logged at DEBUG).
    """
    result = []
    for name in names:
        defn = _TOOL_DEFINITIONS.get(name)
        if defn:
            result.append(defn)
        else:
            import logging
            logging.getLogger(__name__).debug("Unknown tool name: %r", name)
    return result
