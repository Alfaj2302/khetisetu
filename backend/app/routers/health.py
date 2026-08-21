from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import Cursor

from ..db import get_cursor

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/db")
def health_db(cur: Cursor = Depends(get_cursor)) -> dict:
    cur.execute("SELECT count(*) FROM states")
    row = cur.fetchone()
    return {"status": "ok", "states": row[0] if row else 0}
