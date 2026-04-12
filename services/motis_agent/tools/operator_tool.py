"""Operator management tools for the Motis runtime."""

from __future__ import annotations

import inspect
import logging
from typing import Any

from agent.operator_registry import get_operator_registry
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

_OPERATOR_TOOLSET = "motis-operators"


def _registry():
    return get_operator_registry()


def operator_create_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        spec = dict(args.get("spec") or {})
        spec["name"] = args.get("name", spec.get("name", "Untitled Operator"))
        spec["type"] = args.get("type", spec.get("type", "paper_trade"))
        operator_id = _registry().create(spec)
        return tool_result(ok=True, operator_id=operator_id, operator=_registry().get(operator_id))
    except Exception as exc:
        return tool_error(str(exc), ok=False)


def operator_list_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        state_filter = args.get("state_filter", "all")
        operators = _registry().list(state_filter=state_filter)
        return tool_result(operators=operators, count=len(operators))
    except Exception as exc:
        return tool_error(str(exc), ok=False)


def load_operator_tool(args: dict[str, Any], **_kwargs) -> str:
    try:
        return tool_result(
            _registry().load_operator(
                operator_id=args.get("operator_id"),
                name=args.get("name"),
            )
        )
    except Exception as exc:
        return tool_error(str(exc), ok=False)


async def operator_invoke_tool(args: dict[str, Any], **_kwargs) -> str:
    operator_id = str(args.get("operator_id", "") or "")
    if not operator_id:
        return tool_error("operator_id is required", ok=False)

    loaded = _registry().get_loaded_operator(operator_id)
    if loaded is None:
        return tool_error(f"Operator not found: {operator_id}", ok=False)

    try:
        graph = loaded.build_graph()
    except Exception as exc:
        return tool_error(f"Failed to build operator graph: {exc}", ok=False, operator_id=operator_id)

    initial_state = dict(args.get("input") or {})
    if "should_exit" not in initial_state:
        initial_state["should_exit"] = False

    from agent.operator_sdk import (
        complete_operator_run,
        get_operator_run_snapshot,
        reset_operator_runtime,
        set_operator_runtime,
    )

    _registry().update_state(operator_id, "running")
    runtime_token = set_operator_runtime(
        operator_id,
        manifest=loaded.manifest,
        operator=loaded,
    )

    try:
        if hasattr(graph, "ainvoke"):
            result = await graph.ainvoke(initial_state)
        elif callable(graph):
            maybe_result = graph(initial_state)
            result = await maybe_result if inspect.isawaitable(maybe_result) else maybe_result
        else:
            complete_operator_run(status="failed", error="build_graph() returned a non-callable, non-graph object.")
            _registry().update_state(operator_id, "draft")
            return tool_error("build_graph() returned a non-callable, non-graph object.", ok=False, operator_id=operator_id)
    except Exception as exc:
        complete_operator_run(status="failed", error=str(exc))
        _registry().update_state(operator_id, "draft")
        return tool_error(f"Operator execution failed: {exc}", ok=False, operator_id=operator_id)
    finally:
        snapshot = get_operator_run_snapshot(operator_id)
        if snapshot and snapshot.get("status") == "failed":
            reset_operator_runtime(runtime_token)

    complete_operator_run(status="completed", result=result)
    _registry().update_state(operator_id, "complete")
    snapshot = get_operator_run_snapshot(operator_id) or {}
    reset_operator_runtime(runtime_token)

    return tool_result(
        ok=True,
        operator_id=operator_id,
        status=snapshot.get("status", "completed"),
        result=result,
        logs=snapshot.get("recent_logs", []),
        operator=loaded.to_summary_dict(),
    )


def operator_status_tool(args: dict[str, Any], **_kwargs) -> str:
    operator_id = str(args.get("operator_id", "") or "")
    if not operator_id:
        return tool_error("operator_id is required", ok=False)
    operator = _registry().get(operator_id)
    if operator is None:
        return tool_error("Operator not found", ok=False)
    from agent.operator_sdk import get_operator_run_snapshot

    snapshot = get_operator_run_snapshot(operator_id) or {}
    return tool_result(
        operator=operator,
        status=snapshot.get("status", operator.get("state")),
        recent_logs=snapshot.get("recent_logs", []),
        last_run=snapshot or None,
    )


def operator_pause_tool(args: dict[str, Any], **_kwargs) -> str:
    operator_id = str(args.get("operator_id", "") or "")
    if not operator_id:
        return tool_error("operator_id is required", ok=False)
    if _registry().get(operator_id) is None:
        return tool_error("Operator not found", ok=False)
    _registry().update_state(operator_id, "paused")
    return tool_result(ok=True, operator_id=operator_id, state="paused", operator=_registry().get(operator_id))


def operator_archive_tool(args: dict[str, Any], **_kwargs) -> str:
    operator_id = str(args.get("operator_id", "") or "")
    if not operator_id:
        return tool_error("operator_id is required", ok=False)
    if _registry().get(operator_id) is None:
        return tool_error("Operator not found", ok=False)
    _registry().update_state(operator_id, "archived")
    return tool_result(ok=True, operator_id=operator_id, state="archived", operator=_registry().get(operator_id))


def operator_update_prompt_tool(args: dict[str, Any], **_kwargs) -> str:
    operator_id = str(args.get("operator_id", "") or "")
    node_name = str(args.get("node_name", "") or "")
    prompt = str(args.get("prompt", "") or "")
    if not operator_id or not node_name or not prompt:
        return tool_error("operator_id, node_name, and prompt are required", ok=False)

    loaded = _registry().get_loaded_operator(operator_id)
    if loaded is None:
        return tool_error("Operator not found", ok=False)

    reason_prompts = loaded.manifest.setdefault("reason_prompts", {})
    if node_name not in reason_prompts:
        return tool_error(
            f"Node '{node_name}' has no reason_prompt entry in MANIFEST",
            ok=False,
            available_nodes=list(reason_prompts.keys()),
        )

    reason_prompts[node_name] = prompt
    return tool_result(ok=True, operator_id=operator_id, node_name=node_name, message="Prompt updated successfully")


def operator_export_tool(args: dict[str, Any], **_kwargs) -> str:
    operator_id = str(args.get("operator_id", "") or "")
    loaded = _registry().get_loaded_operator(operator_id)
    if loaded is None:
        return tool_error("Operator not found", ok=False)
    source_path = getattr(loaded.module, "__file__", "")
    if not source_path:
        return tool_error("Operator source path is unavailable", ok=False)
    return tool_result(ok=True, operator_id=operator_id, source_path=source_path)


OPERATOR_CREATE_SCHEMA = {
    "name": "operator_create",
    "description": "Create a new operator (research, backtest, paper-trade, or live-trade draft).",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"type": "string", "enum": ["live_trade", "paper_trade", "backtest", "research"]},
            "spec": {"type": "object", "description": "Operator specification including graph_code and optional operator_markdown."},
        },
        "required": ["name", "type", "spec"],
    },
}

OPERATOR_LIST_SCHEMA = {
    "name": "operator_list",
    "description": "List available operators for discovery before loading one in full.",
    "parameters": {
        "type": "object",
        "properties": {
            "state_filter": {
                "type": "string",
                "enum": ["all", "live", "paper", "paused", "draft", "complete", "archived"],
                "default": "all",
            },
        },
    },
}

LOAD_OPERATOR_SCHEMA = {
    "name": "load_operator",
    "description": "Load the full OPERATOR.md card for one operator before invoking it.",
    "parameters": {
        "type": "object",
        "properties": {
            "operator_id": {"type": "string"},
            "name": {"type": "string"},
        },
    },
}

OPERATOR_INVOKE_SCHEMA = {
    "name": "operator_invoke",
    "description": "Run an operator synchronously after inspecting it with load_operator.",
    "parameters": {
        "type": "object",
        "properties": {
            "operator_id": {"type": "string"},
            "input": {"type": "object", "description": "Optional runtime input overrides."},
        },
        "required": ["operator_id"],
    },
}

OPERATOR_STATUS_SCHEMA = {
    "name": "operator_status",
    "description": "Return current operator metadata and recent logs if available.",
    "parameters": {
        "type": "object",
        "properties": {"operator_id": {"type": "string"}},
        "required": ["operator_id"],
    },
}

OPERATOR_PAUSE_SCHEMA = {
    "name": "operator_pause",
    "description": "Pause an operator without deleting it.",
    "parameters": {
        "type": "object",
        "properties": {
            "operator_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["operator_id"],
    },
}

OPERATOR_ARCHIVE_SCHEMA = {
    "name": "operator_archive",
    "description": "Archive an operator.",
    "parameters": {
        "type": "object",
        "properties": {"operator_id": {"type": "string"}},
        "required": ["operator_id"],
    },
}

OPERATOR_UPDATE_PROMPT_SCHEMA = {
    "name": "operator_update_prompt",
    "description": "Hot-patch a REASON-node prompt stored in MANIFEST.reason_prompts.",
    "parameters": {
        "type": "object",
        "properties": {
            "operator_id": {"type": "string"},
            "node_name": {"type": "string"},
            "prompt": {"type": "string"},
        },
        "required": ["operator_id", "node_name", "prompt"],
    },
}

OPERATOR_EXPORT_SCHEMA = {
    "name": "operator_export",
    "description": "Return the filesystem path to an operator's source file.",
    "parameters": {
        "type": "object",
        "properties": {"operator_id": {"type": "string"}},
        "required": ["operator_id"],
    },
}


registry.register("operator_create", _OPERATOR_TOOLSET, OPERATOR_CREATE_SCHEMA, operator_create_tool, emoji="⚙")
registry.register("operator_list", _OPERATOR_TOOLSET, OPERATOR_LIST_SCHEMA, operator_list_tool, emoji="🧾")
registry.register("load_operator", _OPERATOR_TOOLSET, LOAD_OPERATOR_SCHEMA, load_operator_tool, emoji="📘")
registry.register("operator_invoke", _OPERATOR_TOOLSET, OPERATOR_INVOKE_SCHEMA, operator_invoke_tool, is_async=True, emoji="🚀", max_result_size_chars=100_000)
registry.register("operator_status", _OPERATOR_TOOLSET, OPERATOR_STATUS_SCHEMA, operator_status_tool, emoji="📡")
registry.register("operator_pause", _OPERATOR_TOOLSET, OPERATOR_PAUSE_SCHEMA, operator_pause_tool, emoji="⏸")
registry.register("operator_archive", _OPERATOR_TOOLSET, OPERATOR_ARCHIVE_SCHEMA, operator_archive_tool, emoji="📦")
registry.register("operator_update_prompt", _OPERATOR_TOOLSET, OPERATOR_UPDATE_PROMPT_SCHEMA, operator_update_prompt_tool, emoji="✍")
registry.register("operator_export", _OPERATOR_TOOLSET, OPERATOR_EXPORT_SCHEMA, operator_export_tool, emoji="📤")
