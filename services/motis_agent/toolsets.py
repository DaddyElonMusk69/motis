#!/usr/bin/env python3
"""
Toolsets Module

This module provides a flexible system for defining and managing tool aliases/toolsets.
Toolsets allow you to group tools together for specific scenarios and can be composed
from individual tools or other toolsets.

Features:
- Define custom toolsets with specific tools
- Compose toolsets from other toolsets
- Built-in common toolsets for typical use cases
- Easy extension for new toolsets
- Support for dynamic toolset resolution

Usage:
    from toolsets import get_toolset, resolve_toolset, get_all_toolsets
    
    # Get tools for a specific toolset
    tools = get_toolset("research")
    
    # Resolve a toolset to get all tool names (including from composed toolsets)
    all_tools = resolve_toolset("full_stack")
"""

from typing import List, Dict, Any, Set, Optional


# Shared tool list for CLI and all messaging platform toolsets.
# Edit this once to update all platforms simultaneously.
_HERMES_CORE_TOOLS = [
    # Web
    "web_search", "web_extract", "read_url", "web_fetch",
    # Terminal + process management
    "terminal", "process",
    # File manipulation
    "read_file", "write_file", "patch", "search_files",
    # Vision
    "vision_analyze",
    # Skills
    "skills_list", "skill_view", "skill_manage", "list_skills", "load_skill",
    # Motis finance
    "data.resolve_symbol", "data.ohlcv", "data.ticker", "data.orderbook", "data.funding_rate", "data.open_interest",
    "macro.get_series", "equity.get_fundamentals", "equity.get_earnings_calendar", "flows.get_connect", "china.get_moneyflow",
    "smc.structure", "factor_analysis", "options_pricing", "pattern", "pattern_recognition",
    # Motis operators
    "operator_create", "operator_list", "load_operator", "operator_invoke",
    "operator_status", "operator_pause", "operator_archive", "operator_update_prompt", "operator_export",
    # Browser automation
    "browser_navigate", "browser_snapshot", "browser_click",
    "browser_type", "browser_scroll", "browser_back",
    "browser_press", "browser_get_images",
    "browser_vision", "browser_console",
    # Text-to-speech
    "text_to_speech",
    # Planning & memory
    "todo", "memory",
    # Session history search
    "session_search",
    # Clarifying questions
    "clarify",
    # Code execution + delegation
    "execute_code", "delegate_task",
    # Cronjob management
    "cronjob",
    # Cross-platform messaging (gated on gateway running via check_fn)
    "send_message",
]


# Core toolset definitions
# These can include individual tools or reference other toolsets
TOOLSETS = {
    # Basic toolsets - individual tool categories
    "web": {
        "description": "Web research and content extraction tools",
        "tools": ["web_search", "web_extract", "read_url", "web_fetch"],
        "includes": []  # No other toolsets included
    },
    
    "search": {
        "description": "Web search only (no content extraction/scraping)",
        "tools": ["web_search"],
        "includes": []
    },
    
    "vision": {
        "description": "Image analysis and vision tools",
        "tools": ["vision_analyze"],
        "includes": []
    },
    
    "terminal": {
        "description": "Terminal/command execution and process management tools",
        "tools": ["terminal", "process"],
        "includes": []
    },
    
    "moa": {
        "description": "Advanced reasoning and problem-solving tools",
        "tools": ["mixture_of_agents"],
        "includes": []
    },
    
    "skills": {
        "description": "Access, create, edit, and manage skill documents with specialized instructions and knowledge",
        "tools": ["skills_list", "skill_view", "skill_manage", "list_skills", "load_skill"],
        "includes": []
    },

    "motis-finance": {
        "description": "Motis finance runtime tools: structured market data, SMC structure, factor analysis, options pricing, and pattern recognition.",
        "tools": [
            "data.resolve_symbol", "data.ohlcv", "data.ticker", "data.orderbook",
            "data.funding_rate", "data.open_interest",
            "macro.get_series", "equity.get_fundamentals", "equity.get_earnings_calendar",
            "flows.get_connect", "china.get_moneyflow",
            "smc.structure", "factor_analysis", "options_pricing", "pattern", "pattern_recognition",
        ],
        "includes": []
    },

    "motis-operators": {
        "description": "Motis operator lifecycle tools: discover, inspect, invoke, and manage trading operators.",
        "tools": [
            "operator_create", "operator_list", "load_operator", "operator_invoke",
            "operator_status", "operator_pause", "operator_archive",
            "operator_update_prompt", "operator_export",
        ],
        "includes": []
    },
    
    "browser": {
        "description": "Browser automation for web interaction (navigate, click, type, scroll, iframes, hold-click) with web search for finding URLs",
        "tools": [
            "browser_navigate", "browser_snapshot", "browser_click",
            "browser_type", "browser_scroll", "browser_back",
            "browser_press", "browser_get_images",
            "browser_vision", "browser_console", "web_search"
        ],
        "includes": []
    },
    
    "cronjob": {
        "description": "Cronjob management tool - create, list, update, pause, resume, remove, and trigger scheduled tasks",
        "tools": ["cronjob"],
        "includes": []
    },
    
    "messaging": {
        "description": "Cross-platform messaging: send messages to Telegram, Discord, Slack, SMS, etc.",
        "tools": ["send_message"],
        "includes": []
    },
    
    "file": {
        "description": "File manipulation tools: read, write, patch (with fuzzy matching), and search (content + files)",
        "tools": ["read_file", "write_file", "patch", "search_files"],
        "includes": []
    },
    
    "tts": {
        "description": "Text-to-speech: convert text to audio with Edge TTS (free), ElevenLabs, or OpenAI",
        "tools": ["text_to_speech"],
        "includes": []
    },
    
    "todo": {
        "description": "Task planning and tracking for multi-step work",
        "tools": ["todo"],
        "includes": []
    },
    
    "memory": {
        "description": "Persistent memory across sessions (personal notes + user profile)",
        "tools": ["memory"],
        "includes": []
    },
    
    "session_search": {
        "description": "Search and recall past conversations with summarization",
        "tools": ["session_search"],
        "includes": []
    },
    
    "clarify": {
        "description": "Ask the user clarifying questions (multiple-choice or open-ended)",
        "tools": ["clarify"],
        "includes": []
    },
    
    "code_execution": {
        "description": "Run Python scripts that call tools programmatically (reduces LLM round trips)",
        "tools": ["execute_code"],
        "includes": []
    },
    
    "delegation": {
        "description": "Spawn subagents with isolated context for complex subtasks",
        "tools": ["delegate_task"],
        "includes": []
    },

    # "honcho" toolset removed — Honcho is now a memory provider plugin.
    # Tools are injected via MemoryManager, not the toolset system.

    # Scenario-specific toolsets
    
    "debugging": {
        "description": "Debugging and troubleshooting toolkit",
        "tools": ["terminal", "process"],
        "includes": ["web", "file"]  # For searching error messages and solutions, and file operations
    },
    
    "safe": {
        "description": "Safe toolkit without terminal access",
        "tools": [],
        "includes": ["web", "vision"]
    },
    
    # ==========================================================================
    # Full Motis toolsets (CLI + messaging platforms)
    #
    # All platforms share the same core tools (including send_message,
    # which is gated on gateway running via its check_fn).
    # ==========================================================================

    "motis-api-server": {
        "description": "OpenAI-compatible API server — full agent tools accessible via HTTP (no interactive UI tools like clarify or send_message)",
        "tools": [
            # Web
            "web_search", "web_extract", "read_url", "web_fetch",
            # Terminal + process management
            "terminal", "process",
            # File manipulation
            "read_file", "write_file", "patch", "search_files",
            # Vision
            "vision_analyze",
            # Skills
            "skills_list", "skill_view", "skill_manage", "list_skills", "load_skill",
            # Motis finance + operators
            "data.resolve_symbol", "data.ohlcv", "data.ticker", "data.orderbook",
            "data.funding_rate", "data.open_interest",
            "macro.get_series", "equity.get_fundamentals", "equity.get_earnings_calendar",
            "flows.get_connect", "china.get_moneyflow",
            "smc.structure", "factor_analysis", "options_pricing", "pattern", "pattern_recognition",
            "operator_create", "operator_list", "load_operator", "operator_invoke",
            "operator_status", "operator_pause", "operator_archive", "operator_update_prompt", "operator_export",
            # Browser automation
            "browser_navigate", "browser_snapshot", "browser_click",
            "browser_type", "browser_scroll", "browser_back",
            "browser_press", "browser_get_images",
            "browser_vision", "browser_console",
            # Planning & memory
            "todo", "memory",
            # Session history search
            "session_search",
            # Code execution + delegation
            "execute_code", "delegate_task",
            # Cronjob management
            "cronjob",
        ],
        "includes": []
    },
    
    "motis-cli": {
        "description": "Full interactive CLI toolset - all default tools plus cronjob management",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    
    "motis-telegram": {
        "description": "Telegram bot toolset - full access for personal use (terminal has safety checks)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    
    "motis-discord": {
        "description": "Discord bot toolset - full access (terminal has safety checks via dangerous command approval)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    
    "motis-whatsapp": {
        "description": "WhatsApp bot toolset - similar to Telegram (personal messaging, more trusted)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    
    "motis-slack": {
        "description": "Slack bot toolset - full access for workspace use (terminal has safety checks)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    
    "motis-signal": {
        "description": "Signal bot toolset - encrypted messaging platform (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-bluebubbles": {
        "description": "BlueBubbles iMessage bot toolset - Apple iMessage via local BlueBubbles server",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-homeassistant": {
        "description": "Home Assistant bot toolset - smart home event monitoring and control",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-email": {
        "description": "Email bot toolset - interact with Motis via email (IMAP/SMTP)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-mattermost": {
        "description": "Mattermost bot toolset - self-hosted team messaging (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-matrix": {
        "description": "Matrix bot toolset - decentralized encrypted messaging (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-dingtalk": {
        "description": "DingTalk bot toolset - enterprise messaging platform (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-feishu": {
        "description": "Feishu/Lark bot toolset - enterprise messaging via Feishu/Lark (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-wecom": {
        "description": "WeCom bot toolset - enterprise WeChat messaging (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-sms": {
        "description": "SMS bot toolset - interact with Motis via SMS (Twilio)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-webhook": {
        "description": "Webhook toolset - receive and process external webhook events",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "motis-gateway": {
        "description": "Gateway toolset - union of all messaging platform tools",
        "tools": [],
        "includes": ["motis-telegram", "motis-discord", "motis-whatsapp", "motis-slack", "motis-signal", "motis-bluebubbles", "motis-homeassistant", "motis-email", "motis-sms", "motis-mattermost", "motis-matrix", "motis-dingtalk", "motis-feishu", "motis-wecom", "motis-webhook"]
    }
}



def get_toolset(name: str) -> Optional[Dict[str, Any]]:
    """
    Get a toolset definition by name.
    
    Args:
        name (str): Name of the toolset
        
    Returns:
        Dict: Toolset definition with description, tools, and includes
        None: If toolset not found
    """
    # Return toolset definition
    return TOOLSETS.get(name)


def resolve_toolset(name: str, visited: Set[str] = None) -> List[str]:
    """
    Recursively resolve a toolset to get all tool names.
    
    This function handles toolset composition by recursively resolving
    included toolsets and combining all tools.
    
    Args:
        name (str): Name of the toolset to resolve
        visited (Set[str]): Set of already visited toolsets (for cycle detection)
        
    Returns:
        List[str]: List of all tool names in the toolset
    """
    if visited is None:
        visited = set()
    
    # Special aliases that represent all tools across every toolset
    # This ensures future toolsets are automatically included without changes.
    if name in {"all", "*"}:
        all_tools: Set[str] = set()
        for toolset_name in get_toolset_names():
            # Use a fresh visited set per branch to avoid cross-branch contamination
            resolved = resolve_toolset(toolset_name, visited.copy())
            all_tools.update(resolved)
        return list(all_tools)

    # Check for cycles / already-resolved (diamond deps).
    # Silently return [] — either this is a diamond (not a bug, tools already
    # collected via another path) or a genuine cycle (safe to skip).
    if name in visited:
        return []

    visited.add(name)

    # Get toolset definition
    toolset = TOOLSETS.get(name)
    if not toolset:
        # Fall back to tool registry for plugin-provided toolsets
        if name in _get_plugin_toolset_names():
            try:
                from tools.registry import registry
                return [e.name for e in registry._tools.values() if e.toolset == name]
            except Exception:
                pass
        return []

    # Collect direct tools
    tools = set(toolset.get("tools", []))

    # Recursively resolve included toolsets, sharing the visited set across
    # sibling includes so diamond dependencies are only resolved once and
    # cycle warnings don't fire multiple times for the same cycle.
    for included_name in toolset.get("includes", []):
        included_tools = resolve_toolset(included_name, visited)
        tools.update(included_tools)
    
    return list(tools)


def resolve_multiple_toolsets(toolset_names: List[str]) -> List[str]:
    """
    Resolve multiple toolsets and combine their tools.
    
    Args:
        toolset_names (List[str]): List of toolset names to resolve
        
    Returns:
        List[str]: Combined list of all tool names (deduplicated)
    """
    all_tools = set()
    
    for name in toolset_names:
        tools = resolve_toolset(name)
        all_tools.update(tools)
    
    return list(all_tools)


def _get_plugin_toolset_names() -> Set[str]:
    """Return toolset names registered by plugins (from the tool registry).

    These are toolsets that exist in the registry but not in the static
    ``TOOLSETS`` dict — i.e. they were added by plugins at load time.
    """
    try:
        from tools.registry import registry
        return {
            entry.toolset
            for entry in registry._tools.values()
            if entry.toolset not in TOOLSETS
        }
    except Exception:
        return set()


def get_all_toolsets() -> Dict[str, Dict[str, Any]]:
    """
    Get all available toolsets with their definitions.

    Includes both statically-defined toolsets and plugin-registered ones.
    
    Returns:
        Dict: All toolset definitions
    """
    result = TOOLSETS.copy()
    # Add plugin-provided toolsets (synthetic entries)
    for ts_name in _get_plugin_toolset_names():
        if ts_name not in result:
            try:
                from tools.registry import registry
                tools = [e.name for e in registry._tools.values() if e.toolset == ts_name]
                result[ts_name] = {
                    "description": f"Plugin toolset: {ts_name}",
                    "tools": tools,
                }
            except Exception:
                pass
    return result


def get_toolset_names() -> List[str]:
    """
    Get names of all available toolsets (excluding aliases).

    Includes plugin-registered toolset names.
    
    Returns:
        List[str]: List of toolset names
    """
    names = set(TOOLSETS.keys())
    names |= _get_plugin_toolset_names()
    return sorted(names)




def validate_toolset(name: str) -> bool:
    """
    Check if a toolset name is valid.
    
    Args:
        name (str): Toolset name to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Accept special alias names for convenience
    if name in {"all", "*"}:
        return True
    if name in TOOLSETS:
        return True
    # Check tool registry for plugin-provided toolsets
    return name in _get_plugin_toolset_names()


def create_custom_toolset(
    name: str,
    description: str,
    tools: List[str] = None,
    includes: List[str] = None
) -> None:
    """
    Create a custom toolset at runtime.
    
    Args:
        name (str): Name for the new toolset
        description (str): Description of the toolset
        tools (List[str]): Direct tools to include
        includes (List[str]): Other toolsets to include
    """
    TOOLSETS[name] = {
        "description": description,
        "tools": tools or [],
        "includes": includes or []
    }




def get_toolset_info(name: str) -> Dict[str, Any]:
    """
    Get detailed information about a toolset including resolved tools.
    
    Args:
        name (str): Toolset name
        
    Returns:
        Dict: Detailed toolset information
    """
    toolset = get_toolset(name)
    if not toolset:
        return None
    
    resolved_tools = resolve_toolset(name)
    
    return {
        "name": name,
        "description": toolset["description"],
        "direct_tools": toolset["tools"],
        "includes": toolset["includes"],
        "resolved_tools": resolved_tools,
        "tool_count": len(resolved_tools),
        "is_composite": bool(toolset["includes"])
    }




if __name__ == "__main__":
    print("Toolsets System Demo")
    print("=" * 60)
    
    print("\nAvailable Toolsets:")
    print("-" * 40)
    for name, toolset in get_all_toolsets().items():
        info = get_toolset_info(name)
        composite = "[composite]" if info["is_composite"] else "[leaf]"
        print(f"  {composite} {name:20} - {toolset['description']}")
        print(f"     Tools: {len(info['resolved_tools'])} total")
    
    print("\nToolset Resolution Examples:")
    print("-" * 40)
    for name in ["web", "terminal", "safe", "debugging"]:
        tools = resolve_toolset(name)
        print(f"\n  {name}:")
        print(f"    Resolved to {len(tools)} tools: {', '.join(sorted(tools))}")
    
    print("\nMultiple Toolset Resolution:")
    print("-" * 40)
    combined = resolve_multiple_toolsets(["web", "vision", "terminal"])
    print("  Combining ['web', 'vision', 'terminal']:")
    print(f"    Result: {', '.join(sorted(combined))}")
    
    print("\nCustom Toolset Creation:")
    print("-" * 40)
    create_custom_toolset(
        name="my_custom",
        description="My custom toolset for specific tasks",
        tools=["web_search"],
        includes=["terminal", "vision"]
    )
    custom_info = get_toolset_info("my_custom")
    print("  Created 'my_custom' toolset:")
    print(f"    Description: {custom_info['description']}")
    print(f"    Resolved tools: {', '.join(custom_info['resolved_tools'])}")
