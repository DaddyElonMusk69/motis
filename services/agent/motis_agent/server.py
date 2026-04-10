from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from motis_agent.context import UserContext, get_user_context
from motis_agent.core.loop import AgentLoop

app = FastAPI(
    title="Motis Agent Service",
    description="Multi-user master agent — internal service, not public-facing",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Platform gateway handles public CORS
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str


# ── Chat endpoint — streams agent loop messages via SSE ──────────────────────

@app.post("/chat")
async def chat(
    request: ChatRequest,
    ctx: UserContext = Depends(get_user_context),
) -> StreamingResponse:
    """
    Stream the agent's response to a user message.

    Returns Server-Sent Events with agent loop steps:
        - tool_call: agent invoked a tool
        - tool_result: tool returned a result
        - thinking: model reasoning step (if extended thinking enabled)
        - message: final or intermediate text message
        - done: stream complete
    """
    loop = AgentLoop(ctx)

    async def event_stream() -> AsyncGenerator[str, None]:
        async for event in loop.stream(
            message=request.message,
            conversation_id=request.conversation_id,
        ):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Operator introspection (called by platform operator runtime) ──────────────

@app.get("/operators/{operator_id}/state")
async def get_operator_state(
    operator_id: UUID,
    ctx: UserContext = Depends(get_user_context),
) -> dict:
    op = await ctx.operator_registry.get(operator_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")
    return await op.get_state()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "motis-agent"}


def main():
    import uvicorn
    uvicorn.run("motis_agent.server:app", host="0.0.0.0", port=8001, reload=True)
