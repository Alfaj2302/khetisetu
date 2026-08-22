from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

import threading

from .config import CORS_ORIGINS, DATABASE_URL
from .db import pool
from .errors import install_error_handlers
from .routers import auth, business, farmer, health, rag, reference
from .services import embeddings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
            "and fill in your Postgres credentials.",
        )
    pool.open()
    # The local embedding model takes ~24s to load. Off the request path, so the
    # first "Why <crop>?" click does not pay it, and off the boot path in a
    # daemon thread, so /health answers immediately either way. A RAG question
    # arriving before it finishes simply blocks on the same lock.
    threading.Thread(target=embeddings.warm_up, name="embeddings-warmup", daemon=True).start()
    try:
        yield
    finally:
        pool.close()


app = FastAPI(
    title="FasalCast / KhetiSetu API",
    version="1.0.0",
    description="Farmer recommendation, business dashboard, and RAG endpoints for KhetiSetu.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


app.include_router(health.router)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(reference.router)
api_v1.include_router(farmer.router)
api_v1.include_router(business.router)
api_v1.include_router(rag.router)

app.include_router(api_v1)
