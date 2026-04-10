"""
Motis Agent Service — FastAPI Server
=====================================
Internal service. Not public-facing — sits behind the platform gateway.
The gateway validates JWT, resolves user identity, and forwards requests
here with trusted X-User-* headers.

Endpoints:
  POST /chat             Stream agent responses via SSE
  GET  /memories         List/search a user's memories
  POST /memories         Add a memory explicitly
  DELETE /memories/{id}  Delete a memory
  GET  /health           Health check

SSE event format (newline-delimited JSON, text/event-stream):
  data: {"type": "message_start", "ts": 1712345678.0, "conversation_id": "..."}
  data: {"type": "thinking", "ts": ..., "text": "..."}
  data: {"type": "tool_call", "ts": ..., "tool": "web_search", "args": {...}}
  data: {"type": "tool_result", "ts": ..., "tool": "web_search", "result": {...}, "ok": true}
  data: {"type": "text_delta", "ts": ..., "text": "..."}
  data: {"type": "message_end", "ts": ..., "stop_reason": "stop"}
  data: {"type": "done"}
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from motis_agent.context import UserContext, get_user_context
from motis_agent.core.loop import MotisAgentLoop
from motis_agent.core.memory import MemoryStore, _engine

logger = logging.getLogger(__name__)


# ── Lifespan: pool warm-up and teardown ──────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the DB connection pool on startup
    logger.info("Motis Agent Service starting — warming DB pool")
    async with _engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    logger.info("DB pool ready")
    yield
    # Dispose pool on shutdown
    await _engine.dispose()
    logger.info("Motis Agent Service stopped")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Motis Agent Service",
    description=(
        "Multi-user master agent — internal service, not public-facing.\n\n"
        "Sits behind the platform gateway. JWT validation happens at the gateway; "
        "this service trusts the X-User-* headers it receives."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Platform gateway handles public CORS — only allow internal callers here
    allow_origins=["http://localhost:3000", "http://platform:8000"],
    allow_methods=["POST", "GET", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32_000)


class MemoryAddRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8_000)
    type: str = Field(default="general")
    tags: list[str] = Field(default_factory=list)
    importance: int = Field(default=5, ge=1, le=10)


class MemoryResponse(BaseModel):
    id: str
    content: str
    type: str
    tags: list[str]
    importance: int
    created_at: str


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.post(
    "/chat",
    summary="Stream agent response via SSE",
    response_description="Server-Sent Events stream of agent loop events",
)
async def chat(
    request: ChatRequest,
    ctx: UserContext = Depends(get_user_context),
) -> StreamingResponse:
    """
    Process a user message through the Motis Master Agent and stream the response.

    Each SSE event is a JSON object with at minimum {"type": str, "ts": float}.
    The stream ends with {"type": "done"}.

    The conversation_id in the response events comes from the X-Conversation-Id
    header passed by the platform gateway (or a fresh UUID if not provided).
    """
    loop = MotisAgentLoop(ctx)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in loop.stream(request.message):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:
            logger.error(
                "Agent loop error for user %s: %s", ctx.user_id, exc, exc_info=True
            )
            error_event = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # Disable nginx buffering for SSE
            "X-Conversation-Id": str(ctx.conversation_id),
        },
    )


# ── Memory endpoints ──────────────────────────────────────────────────────────

@app.get(
    "/memories",
    summary="Search or list user memories",
)
async def list_memories(
    q: str = Query(default="", description="Full-text search query"),
    limit: int = Query(default=20, ge=1, le=100),
    type: str | None = Query(default=None, description="Filter by memory type"),
    ctx: UserContext = Depends(get_user_context),
) -> dict:
    """
    Return the user's memories, ranked by relevance (if query given) or recency.
    """
    if q:
        entries = await ctx.memory.search(q, limit=limit, type_filter=type)
    else:
        entries = await ctx.memory.recent(limit=limit, type_filter=type)

    return {
        "memories": [e.model_dump() for e in entries],
        "total": await ctx.memory.count(),
    }


@app.post(
    "/memories",
    summary="Explicitly add a memory",
    status_code=201,
)
async def add_memory(
    body: MemoryAddRequest,
    ctx: UserContext = Depends(get_user_context),
) -> dict:
    """
    Explicitly add a memory (user-initiated or platform-triggered).
    The agent also adds memories autonomously via the memory_add tool.
    """
    memory_id = await ctx.memory.add(
        content=body.content,
        type=body.type,
        tags=body.tags,
        importance=body.importance,
        source="user",
    )
    return {"id": str(memory_id), "ok": True}


@app.delete(
    "/memories/{memory_id}",
    summary="Delete a specific memory",
)
async def delete_memory(
    memory_id: UUID,
    ctx: UserContext = Depends(get_user_context),
) -> dict:
    """Delete a specific memory. 404 if not found or not owned by this user."""
    deleted = await ctx.memory.delete(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


# ── Operator introspection ────────────────────────────────────────────────────

@app.get(
    "/operators/{operator_id}/state",
    summary="Get operator state (called by platform operator runtime)",
)
async def get_operator_state(
    operator_id: UUID,
    ctx: UserContext = Depends(get_user_context),
) -> dict:
    """
    Returns the current LangGraph state snapshot for a running operator.
    Called by the platform's operator runtime worker to stream state to the frontend.
    """
    op = await ctx.operator_registry.get(operator_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")
    return await op.get_state()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
async def health() -> dict:
    return {"status": "ok", "service": "motis-agent", "version": "0.2.0"}


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    import uvicorn
    uvicorn.run(
        "motis_agent.server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
