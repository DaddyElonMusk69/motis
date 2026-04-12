from __future__ import annotations

import sys
from pathlib import Path


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

from agent import motis_prompt
from agent.operator_sdk import _build_agent_system_prompt


def test_operator_guidance_defines_operators_as_durable_workflows() -> None:
    guidance = motis_prompt.OPERATOR_TOOL_GUIDANCE

    assert "solidified agentic workflow" in guidance
    assert "durable, inspectable workflow unit" in guidance
    assert "from the user's explicit instructions" in guidance
    assert "from extensive research" in guidance
    assert "not just a note, a one-off prompt, or a loose automation script" in guidance


def test_runtime_prompt_includes_operator_nature_when_operator_tools_present() -> None:
    prompt = motis_prompt.build_motis_runtime_prompt({"operator_create"})

    assert "solidified agentic workflow" in prompt
    assert "first-class runtime artifact" in prompt


def test_runtime_prompt_lists_structured_market_tools() -> None:
    prompt = motis_prompt.build_motis_runtime_prompt({"data.ticker"})

    assert "`data.ticker`" in prompt
    assert "Prefer structured market and dataset tools over narrative web search" in prompt
    assert "`data.resolve_symbol`" not in prompt
    assert "`data.orderbook`" not in prompt


def test_runtime_prompt_lists_structured_research_tools() -> None:
    prompt = motis_prompt.build_motis_runtime_prompt({"macro.get_series"})

    assert "`macro.get_series`" in prompt
    assert "Prefer structured market and dataset tools over narrative web search" in prompt
    assert "`equity.get_fundamentals`" not in prompt


def test_runtime_prompt_does_not_advertise_missing_finance_tools_when_only_web_exists() -> None:
    prompt = motis_prompt.build_motis_runtime_prompt({"web_search"})

    assert "Finance Runtime Limited:" in prompt
    assert "`web_search`" in prompt
    assert "`data.ticker`" not in prompt
    assert "`data.resolve_symbol`" not in prompt


def test_operator_subagent_prompt_frames_operator_as_runtime_unit() -> None:
    prompt = _build_agent_system_prompt(
        agent_id="researcher",
        agent_config={"system_prompt": "Focus on macro catalysts."},
        context={},
        unavailable_tools=(),
    )

    assert "working inside a Motis operator" in prompt
    assert "durable, stateful agentic workflow" in prompt
    assert "distilled from extensive research" in prompt
