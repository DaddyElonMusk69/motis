from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

import run_agent as run_agent_module


class _BrokenStream:
    response = None

    def __iter__(self):
        yield SimpleNamespace(
            model="demo-model",
            usage=None,
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content="Partial answer",
                        reasoning_content=None,
                        reasoning=None,
                        tool_calls=None,
                    ),
                    finish_reason=None,
                )
            ],
        )
        raise ConnectionError("stream dropped")


class _FakeCompletions:
    def create(self, **kwargs):
        return _BrokenStream()


class _FakeChat:
    completions = _FakeCompletions()


class _FakeClient:
    chat = _FakeChat()


def test_partial_stream_failure_returns_truncated_response_for_continuation() -> None:
    streamed: list[str] = []

    agent = run_agent_module.AIAgent.__new__(run_agent_module.AIAgent)
    agent.api_mode = "chat_completions"
    agent.base_url = ""
    agent.model = "demo-model"
    agent.provider = "custom"
    agent._interrupt_requested = False
    agent._stream_needs_break = False
    agent.stream_delta_callback = streamed.append
    agent._stream_callback = None
    agent.reasoning_callback = None
    agent.tool_gen_callback = None
    agent._create_request_openai_client = lambda reason=None: _FakeClient()
    agent._capture_rate_limits = lambda response: None
    agent._touch_activity = lambda desc: None
    agent._close_request_openai_client = lambda client, reason=None: None
    agent._replace_primary_openai_client = lambda reason=None: None
    agent._emit_status = lambda message: None
    agent._safe_print = lambda *args, **kwargs: None

    response = agent._interruptible_streaming_api_call(
        {"messages": [], "model": "demo-model"}
    )

    assert streamed == ["Partial answer"]
    assert response.choices[0].message.content == "Partial answer"
    assert response.choices[0].finish_reason == "length"
