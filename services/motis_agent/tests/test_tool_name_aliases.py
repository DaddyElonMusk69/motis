from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

import run_agent as run_agent_module


def _make_tool(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"tool {name}",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _make_agent(tool_names: list[str]):
    agent = run_agent_module.AIAgent.__new__(run_agent_module.AIAgent)
    agent.tools = [_make_tool(name) for name in tool_names]
    agent.valid_tool_names = set(tool_names)
    agent._api_tool_name_alias_to_canonical = {}
    agent._api_tool_name_canonical_to_alias = {}
    agent._refresh_tool_name_alias_maps()
    return agent


def test_tools_for_api_sanitizes_dotted_names() -> None:
    agent = _make_agent(["data.ohlcv", "memory"])

    translated = agent._tools_for_api()

    assert translated is not None
    assert translated[0]["function"]["name"] == "data_ohlcv"
    assert translated[1]["function"]["name"] == "memory"
    assert agent._canonical_tool_name("data_ohlcv") == "data.ohlcv"


def test_normalize_assistant_tool_call_names_restores_internal_name() -> None:
    agent = _make_agent(["data.ohlcv"])
    assistant_message = SimpleNamespace(
        tool_calls=[
            SimpleNamespace(
                function=SimpleNamespace(name="data_ohlcv", arguments='{"symbol":"BTCUSDT"}')
            )
        ]
    )

    agent._normalize_assistant_tool_call_names(assistant_message)

    assert assistant_message.tool_calls[0].function.name == "data.ohlcv"


def test_tool_name_aliases_avoid_collisions() -> None:
    agent = _make_agent(["data.ohlcv", "data_ohlcv"])

    dotted_alias = agent._api_safe_tool_name("data.ohlcv")
    plain_alias = agent._api_safe_tool_name("data_ohlcv")

    assert dotted_alias != plain_alias
    assert agent._canonical_tool_name(dotted_alias) == "data.ohlcv"
    assert agent._canonical_tool_name(plain_alias) == "data_ohlcv"


def test_repair_tool_call_accepts_provider_safe_aliases() -> None:
    agent = _make_agent(["data.ohlcv", "macro.get_series"])

    assert agent._repair_tool_call("data_ohlcv") == "data.ohlcv"
    assert agent._repair_tool_call("macro_get_series") == "macro.get_series"


def test_responses_tools_use_provider_safe_names() -> None:
    agent = _make_agent(["data.ohlcv", "macro.get_series"])

    converted = agent._responses_tools()

    assert converted is not None
    assert [tool["name"] for tool in converted] == ["data_ohlcv", "macro_get_series"]


def test_build_api_kwargs_uses_provider_safe_tool_names() -> None:
    agent = _make_agent(["data.ohlcv", "macro.get_series"])
    agent.api_mode = "chat_completions"
    agent.model = "gpt-4o-mini"
    agent.base_url = "https://example.com/v1"
    agent._base_url_lower = agent.base_url.lower()
    agent.session_id = "test-session"
    agent.providers_allowed = []
    agent.providers_ignored = []
    agent.providers_order = []
    agent.provider_sort = None
    agent.provider_require_parameters = False
    agent.provider_data_collection = None
    agent.max_tokens = None
    agent.reasoning_config = None
    agent._is_qwen_portal = lambda: False
    agent._is_openrouter_url = lambda: False

    kwargs = agent._build_api_kwargs(
        [
            {"role": "system", "content": "You are Motis."},
            {"role": "user", "content": "Fetch CPI and OHLCV."},
        ]
    )

    assert [tool["function"]["name"] for tool in kwargs["tools"]] == [
        "data_ohlcv",
        "macro_get_series",
    ]
