from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from motis_platform.api.routes import operators, chat, arena, marketplace
from motis_platform.api.middleware.auth import AuthMiddleware

app = FastAPI(
    title="Motis Platform API",
    description="Public-facing gateway for the Motis trading platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Override in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)

# Routes
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(operators.router, prefix="/api/operators", tags=["Operators"])
app.include_router(arena.router, prefix="/api/arena", tags=["Arena"])
app.include_router(marketplace.router, prefix="/api/marketplace", tags=["Marketplace"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "motis-platform"}


def main():
    import uvicorn
    uvicorn.run("motis_platform.api.app:app", host="0.0.0.0", port=8000, reload=True)
