"""
Motis Sub-agent Delegation
==========================
Adapted from NousResearch/hermes-agent tools/delegate_tool.py (MIT License)

Key changes vs. Hermes:
- Spawns MotisAgentLoop instances (not AIAgent) 
- Shares the parent's UserContext (same user memory + operators)
- Fully async (asyncio.gather instead of ThreadPoolExecutor)
- No Docker/Modal/SSH execution backends (Hermes has 6; we need 1)
- No process-global tool name mutation (Hermes has a known thread-safety workaround)
- Depth limit enforced via sub_depth parameter (not a global _delegate_depth attr)

Design:
  Parent agent calls delegate_task(tasks=[{goal, context, tools}])
  → SubagentRunner spawns N MotisAgentLoop instances asynchronously
  → Each sub-agent gets the full UserContext but its own conversation messages
  → Results collected and returned as structured JSON to the parent
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from motis_agent.context import UserContext

logger = logging.getLogger(__name__)

MAX_CONCURRENT_CHILDREN = 3  # Match Hermes's default
MAX_SUB_DEPTH = 2             # parent(0) → child(1) → grandchild rejected


async def motis_delegate_task(
    args: dict,
    ctx: UserContext,
    sub_depth: int,
) -> dict:
    """
    Entry point called by MotisToolRouter for the delegate_task tool.

    args schema:
        goal (str): Single task goal (for single-task mode)
        context (str, optional): Additional context for the sub-agent
        tasks (list[{goal, context}], optional): Multiple tasks (batch mode)
        max_turns (int, optional): Per-sub-agent turn limit (default: 20)
    """
    if sub_depth >= MAX_SUB_DEPTH:
        return {
            "error": f"Delegation depth limit ({MAX_SUB_DEPTH}) reached. "
                     "Sub-agents cannot spawn further sub-agents."
        }

    max_turns = int(args.get("max_turns", 20))

    # Normalise to task list (single or batch mode — same as Hermes)
    if "tasks" in args and isinstance(args["tasks"], list):
        task_list = args["tasks"][:MAX_CONCURRENT_CHILDREN]
    elif "goal" in args and args["goal"]:
        task_list = [{"goal": args["goal"], "context": args.get("context", "")}]
    else:
        return {"error": "Provide either 'goal' (single task) or 'tasks' (batch)."}

    if not task_list:
        return {"error": "No tasks provided."}

    overall_start = time.monotonic()

    coros = [
        _run_single_subagent(
            task_index=i,
            goal=t["goal"],
            context=t.get("context", ""),
            max_turns=max_turns,
            ctx=ctx,
            sub_depth=sub_depth,
        )
        for i, t in enumerate(task_list)
    ]

    results = await asyncio.gather(*coros, return_exceptions=True)

    # Convert exceptions to error dicts (same structure as Hermes)
    structured = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            structured.append({
                "task_index": i,
                "status": "error",
                "summary": None,
                "error": str(result),
                "duration_seconds": 0,
            })
        else:
            structured.append(result)
            if result.get("summary"):
                await ctx.memory_manager.on_delegation(
                    task=task_list[i]["goal"],
                    result=result["summary"],
                    child_session_id=f"{ctx.conversation_id}:{i}",
                )

    total_duration = round(time.monotonic() - overall_start, 2)
    return {
        "results": structured,
        "total_duration_seconds": total_duration,
    }


async def _run_single_subagent(
    task_index: int,
    goal: str,
    context: str,
    max_turns: int,
    ctx: UserContext,
    sub_depth: int,
) -> dict:
    """
    Run a single sub-agent loop to completion.

    Adapted from Hermes _run_single_child():
    - Uses MotisAgentLoop instead of AIAgent
    - Collects all events and extracts the final text response
    - Returns a structured result dict matching Hermes's format

    Key design choice: sub-agents share the parent's UserContext (same user memory,
    same operators, same model config). They get their own conversation messages.
    This is intentional — want sub-agents to be able to read the user's memories
    and operator list, but not the parent conversation that spawned them.
    """
    from motis_agent.core.loop import MotisAgentLoop, _event

    start = time.monotonic()

    # Inject context into the goal prompt (same as Hermes's _build_child_system_prompt)
    full_prompt = goal
    if context:
        full_prompt = f"{goal}\n\nContext:\n{context}"

    child_loop = MotisAgentLoop(ctx, sub_depth=sub_depth)
    child_loop.MAX_TURNS = max_turns  # cap per-child turn budget

    events = []
    final_text = ""
    try:
        async for event in child_loop.stream(full_prompt):
            events.append(event)
            if event["type"] == "text_delta":
                final_text += event.get("text", "")
    except Exception as exc:
        duration = round(time.monotonic() - start, 2)
        logger.error("Sub-agent %d failed: %s", task_index, exc, exc_info=True)
        return {
            "task_index": task_index,
            "status": "error",
            "summary": None,
            "error": str(exc),
            "duration_seconds": duration,
        }

    duration = round(time.monotonic() - start, 2)
    tool_trace = [
        {"tool": e["tool"], "ok": e.get("ok", True)}
        for e in events
        if e["type"] == "tool_result"
    ]

    return {
        "task_index": task_index,
        "status": "completed" if final_text else "no_response",
        "summary": final_text,
        "duration_seconds": duration,
        "tool_trace": tool_trace,
    }
