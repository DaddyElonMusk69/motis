"""Internal Motis operator runtime helpers."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import logging
from typing import Any, Mapping
import uuid

from agent.runtime_context import get_current_agent

logger = logging.getLogger(__name__)

_current_runtime: ContextVar["OperatorRuntime | None"] = ContextVar(
    "motis_agent_operator_runtime",
    default=None,
)
_latest_operator_runs: dict[str, dict[str, Any]] = {}


@dataclass(slots=True)
class AgentResult:
    """Normalized sub-agent return shape expected by bundled operators."""

    agent_id: str
    summary: str
    raw_response: str
    model: str
    toolsets: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()


@dataclass(slots=True)
class OperatorRuntime:
    """Per-invocation operator runtime context."""

    operator_id: str
    manifest: dict[str, Any]
    operator: Any
    parent_agent: Any | None = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logs: list[dict[str, Any]] = field(default_factory=list)


class _SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def set_operator_runtime(
    operator_id: str,
    *,
    manifest: dict[str, Any],
    operator: Any,
    parent_agent: Any | None = None,
) -> Token["OperatorRuntime | None"]:
    """Bind operator runtime context for SDK calls during one invocation."""
    runtime = OperatorRuntime(
        operator_id=operator_id,
        manifest=manifest,
        operator=operator,
        parent_agent=parent_agent or get_current_agent(),
    )
    _latest_operator_runs[operator_id] = {
        "run_id": runtime.run_id,
        "operator_id": operator_id,
        "status": "running",
        "started_at": runtime.started_at.isoformat(),
        "finished_at": None,
        "recent_logs": [],
        "result": None,
        "error": None,
    }
    return _current_runtime.set(runtime)


def reset_operator_runtime(token: Token["OperatorRuntime | None"]) -> None:
    """Restore the previous operator runtime context."""
    _current_runtime.reset(token)


def get_runtime() -> OperatorRuntime:
    runtime = _current_runtime.get()
    if runtime is None:
        raise RuntimeError("agent.operator_sdk was used outside an active operator invocation")
    return runtime


def complete_operator_run(
    *,
    status: str,
    result: Any | None = None,
    error: str | None = None,
) -> None:
    """Persist the latest completed run snapshot for operator_status()."""
    runtime = _current_runtime.get()
    if runtime is None:
        return

    snapshot = _latest_operator_runs.setdefault(runtime.operator_id, {})
    snapshot.update(
        {
            "run_id": runtime.run_id,
            "operator_id": runtime.operator_id,
            "status": status,
            "started_at": runtime.started_at.isoformat(),
            "finished_at": _utc_now_iso(),
            "recent_logs": list(runtime.logs[-50:]),
            "result": result,
            "error": error,
        }
    )


def get_operator_run_snapshot(operator_id: str) -> dict[str, Any] | None:
    """Return the latest operator run snapshot, if present."""
    snapshot = _latest_operator_runs.get(str(operator_id))
    if snapshot is None:
        return None
    return dict(snapshot)


def get_manifest() -> dict[str, Any]:
    """Return the active operator MANIFEST, including hot-patched prompts."""
    return get_runtime().manifest


def log_event(node: str, message: str, data: Any | None = None, level: str = "info") -> None:
    """Append a structured log event to the current operator run."""
    runtime = get_runtime()
    event = {
        "timestamp": _utc_now_iso(),
        "run_id": runtime.run_id,
        "node": str(node or "").strip() or "operator",
        "level": str(level or "info").lower(),
        "message": str(message or ""),
    }
    if data is not None:
        event["data"] = data
    runtime.logs.append(event)


def _model_config_default() -> str:
    try:
        from motis_cli.config import load_config

        config = load_config()
        model_cfg = config.get("model")
        if isinstance(model_cfg, dict):
            value = model_cfg.get("default") or model_cfg.get("model") or ""
            return str(value or "").strip()
        if isinstance(model_cfg, str):
            return model_cfg.strip()
    except Exception:
        pass
    return ""


def _tool_name_to_toolset(tool_name: str) -> str | None:
    normalized = str(tool_name or "").strip()
    if not normalized:
        return None

    try:
        from model_tools import get_toolset_for_tool

        resolved = get_toolset_for_tool(normalized)
        if resolved:
            return resolved
    except Exception:
        pass

    aliases = {
        "bash": "terminal",
        "terminal": "terminal",
        "process": "terminal",
        "read_file": "file",
        "write_file": "file",
        "patch": "file",
        "edit_file": "file",
        "search_files": "file",
        "load_skill": "skills",
        "list_skills": "skills",
        "skill_view": "skills",
        "skills_list": "skills",
        "read_url": "web",
        "web_fetch": "web",
        "web_extract": "web",
        "web_search": "web",
        "data.resolve_symbol": "motis-finance-data",
        "data.ohlcv": "motis-finance-data",
        "data.ticker": "motis-finance-data",
        "data.orderbook": "motis-finance-data",
        "data.funding_rate": "motis-finance-data",
        "data.open_interest": "motis-finance-data",
        "macro.get_series": "motis-finance-data",
        "equity.get_fundamentals": "motis-finance-data",
        "equity.get_earnings_calendar": "motis-finance-data",
        "flows.get_connect": "motis-finance-data",
        "china.get_moneyflow": "motis-finance-data",
        "smc.structure": "motis-finance",
        "factor_analysis": "motis-finance",
        "options_pricing": "motis-finance",
        "pattern": "motis-finance",
        "pattern_recognition": "motis-finance",
    }
    return aliases.get(normalized)


def _resolve_requested_toolsets(tool_names: list[str] | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    requested = [str(name).strip() for name in (tool_names or []) if str(name).strip()]
    resolved: list[str] = []
    unavailable: list[str] = []
    for tool_name in requested:
        toolset = _tool_name_to_toolset(tool_name)
        if toolset is None:
            unavailable.append(tool_name)
            continue
        if toolset not in resolved:
            resolved.append(toolset)
    return tuple(resolved), tuple(unavailable)


def _build_agent_system_prompt(
    *,
    agent_id: str,
    agent_config: Mapping[str, Any],
    context: Mapping[str, Any],
    unavailable_tools: tuple[str, ...],
) -> str:
    template = str(agent_config.get("system_prompt") or "").strip()
    rendered = template.format_map(_SafeFormatDict({k: v for k, v in context.items()}))

    requested_tools = [str(item).strip() for item in (agent_config.get("tools") or []) if str(item).strip()]
    requested_skills = [str(item).strip() for item in (agent_config.get("skills") or []) if str(item).strip()]

    notes = [
        "You are working inside a Motis operator.",
        "An operator is a durable, stateful agentic workflow with an explicit mandate, graph structure, constraints, and lifecycle.",
        "Operators may be directly authored from user instructions or distilled from extensive research into a reusable operating workflow.",
        "Treat the operator as a real runtime unit with ownership of its role, context, safeguards, and outputs.",
        "",
        rendered,
        "",
        "Runtime policy:",
        "- Stay inside the Motis logical tool interface exposed to you.",
        "- Do not fabricate backtest or execution results.",
        "- Backtest and signal-engine execution are intentionally not wired in this runtime yet; if asked for those, state the limitation clearly and continue with research/design work only.",
    ]
    if requested_tools:
        notes.append(f"- Requested tool contract: {', '.join(requested_tools)}")
    if requested_skills:
        notes.append(f"- Requested skills context: {', '.join(requested_skills)}")
    if unavailable_tools:
        notes.append(f"- Unavailable in this runtime today: {', '.join(unavailable_tools)}")
    notes.append(f"- Agent id: {agent_id}")
    return "\n".join(part for part in notes if part is not None).strip()


def _build_agent_user_message(context: Mapping[str, Any]) -> str:
    if not context:
        return "Execute your assigned role and return a concise, actionable result."

    pretty = json.dumps(dict(context), ensure_ascii=False, indent=2, default=str)
    return (
        "Use this operator context to complete your assigned role.\n\n"
        f"{pretty}\n\n"
        "Return the final analysis directly."
    )


def _build_child_agent(
    *,
    model_name: str,
    system_prompt: str,
    enabled_toolsets: tuple[str, ...],
    max_iterations: int,
):
    from run_agent import AIAgent
    from motis_cli.runtime_provider import resolve_runtime_provider

    parent_agent = get_current_agent()

    if parent_agent is not None:
        base_url = getattr(parent_agent, "base_url", "")
        api_key = getattr(parent_agent, "api_key", None)
        provider = getattr(parent_agent, "provider", None)
        api_mode = getattr(parent_agent, "api_mode", None)
        platform = getattr(parent_agent, "platform", None)
        session_db = getattr(parent_agent, "_session_db", None)
        parent_session_id = getattr(parent_agent, "session_id", None)
        providers_allowed = getattr(parent_agent, "providers_allowed", None)
        providers_ignored = getattr(parent_agent, "providers_ignored", None)
        providers_order = getattr(parent_agent, "providers_order", None)
        provider_sort = getattr(parent_agent, "provider_sort", None)
        max_tokens = getattr(parent_agent, "max_tokens", None)
        reasoning_config = getattr(parent_agent, "reasoning_config", None)
        prefill_messages = getattr(parent_agent, "prefill_messages", None)
        print_fn = getattr(parent_agent, "_print_fn", None)
    else:
        runtime = resolve_runtime_provider()
        base_url = runtime.get("base_url", "")
        api_key = runtime.get("api_key")
        provider = runtime.get("provider")
        api_mode = runtime.get("api_mode")
        platform = None
        session_db = None
        parent_session_id = None
        providers_allowed = None
        providers_ignored = None
        providers_order = None
        provider_sort = None
        max_tokens = None
        reasoning_config = None
        prefill_messages = None
        print_fn = None

    child = AIAgent(
        base_url=base_url,
        api_key=api_key,
        provider=provider,
        api_mode=api_mode,
        model=model_name,
        max_iterations=max_iterations,
        max_tokens=max_tokens,
        reasoning_config=reasoning_config,
        prefill_messages=prefill_messages,
        enabled_toolsets=list(enabled_toolsets),
        quiet_mode=True,
        ephemeral_system_prompt=system_prompt,
        platform=platform,
        skip_context_files=True,
        skip_memory=True,
        clarify_callback=None,
        session_db=session_db,
        parent_session_id=parent_session_id,
        providers_allowed=providers_allowed,
        providers_ignored=providers_ignored,
        providers_order=providers_order,
        provider_sort=provider_sort,
    )
    child._print_fn = print_fn
    return child


async def run_agent(
    agent_id: str,
    context: dict[str, Any],
    *,
    output_key: str = "summary",
) -> AgentResult:
    """Spawn a scoped sub-agent for a MANIFEST-declared operator role."""
    runtime = get_runtime()
    agents = runtime.manifest.get("agents") or {}
    agent_config = agents.get(agent_id)
    if not isinstance(agent_config, Mapping):
        raise KeyError(f"Unknown operator agent: {agent_id}")

    toolsets, unavailable_tools = _resolve_requested_toolsets(agent_config.get("tools"))
    skills = tuple(str(item).strip() for item in (agent_config.get("skills") or []) if str(item).strip())
    model_name = str(agent_config.get("model_name") or "").strip() or getattr(
        get_current_agent(), "model", ""
    ) or _model_config_default()
    max_iterations = int(agent_config.get("max_iterations") or 25)

    system_prompt = _build_agent_system_prompt(
        agent_id=agent_id,
        agent_config=agent_config,
        context=context or {},
        unavailable_tools=unavailable_tools,
    )
    user_message = _build_agent_user_message(context or {})

    log_event(
        agent_id,
        "Starting sub-agent",
        {
            "role": agent_config.get("role", agent_id),
            "toolsets": list(toolsets),
            "skills": list(skills),
            "unavailable_tools": list(unavailable_tools),
        },
    )

    child = _build_child_agent(
        model_name=model_name,
        system_prompt=system_prompt,
        enabled_toolsets=toolsets,
        max_iterations=max_iterations,
    )
    response = await asyncio.to_thread(child.chat, user_message)
    summary = response if output_key == "summary" else response

    log_event(
        agent_id,
        "Completed sub-agent",
        {"chars": len(summary), "output_key": output_key},
    )

    return AgentResult(
        agent_id=agent_id,
        summary=summary,
        raw_response=response,
        model=model_name,
        toolsets=toolsets,
        skills=skills,
    )


def _parse_tool_result(payload: str) -> Any:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload

    if isinstance(parsed, dict) and parsed.get("error"):
        raise RuntimeError(str(parsed["error"]))
    return parsed


async def call_skill(name: str, args: dict[str, Any]) -> Any:
    """Call a Motis tool or skill from operator code and return Python data."""
    tool_name = str(name or "").strip()
    if not tool_name:
        raise ValueError("call_skill() requires a tool name")

    if tool_name == "backtest":
        raise RuntimeError(
            "Backtest is intentionally deferred in this runtime. "
            "Cross-reference the Vibe Trading architecture docs, but do not fabricate backtest output."
        )

    parent_agent = get_current_agent()
    session_id = getattr(parent_agent, "session_id", "") if parent_agent is not None else ""

    from model_tools import handle_function_call

    payload = await asyncio.to_thread(
        handle_function_call,
        tool_name,
        dict(args or {}),
        None,
        None,
        session_id,
        None,
        None,
    )
    parsed = _parse_tool_result(payload)
    if tool_name == "data.ohlcv" and isinstance(parsed, dict) and "candles" in parsed:
        return parsed["candles"]
    return parsed


def _extract_json_block(text: str) -> Any:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
    cleaned = cleaned.strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


async def reason_call(
    *,
    prompt: str,
    response_format: dict[str, Any] | None = None,
    model_name: str | None = None,
    max_iterations: int = 1,
) -> Any:
    """Run a single model call for REASON nodes."""
    parent_agent = get_current_agent()
    effective_model = str(model_name or "").strip() or getattr(parent_agent, "model", "") or _model_config_default()
    child = _build_child_agent(
        model_name=effective_model,
        system_prompt=(
            "You are a precise reasoning worker inside a Motis operator. "
            "The operator is a durable workflow with a specific mandate, constraints, and state context. "
            "Respect that scope, answer directly, and follow the requested response format exactly."
        ),
        enabled_toolsets=(),
        max_iterations=max_iterations,
    )
    response = await asyncio.to_thread(child.chat, str(prompt or ""))
    if response_format and response_format.get("type") == "json_object":
        try:
            return _extract_json_block(response)
        except Exception as exc:
            raise RuntimeError(f"reason_call expected JSON output but could not parse it: {exc}") from exc
    return response


async def submit_order(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """Deferred execution surface until execution MCP / engines are wired."""
    raise RuntimeError(
        "submit_order() is intentionally deferred. "
        "Execution, backtest, and signal-engine backends are not wired in this runtime yet."
    )
