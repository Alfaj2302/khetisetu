from __future__ import annotations

from collections.abc import Iterator

from psycopg import Cursor
from psycopg_pool import ConnectionPool

from .config import DATABASE_URL

# open=False: don't connect at import time (matters for uvicorn's --reload
# subprocess, which re-imports this module before the app lifespan runs).
pool = ConnectionPool(conninfo=DATABASE_URL or "", open=False, min_size=1, max_size=5)


def get_cursor() -> Iterator[Cursor]:
    with pool.connection() as conn, conn.cursor() as cur:
        yield cur
