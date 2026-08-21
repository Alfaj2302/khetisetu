from __future__ import annotations

from collections.abc import Iterator

from psycopg import Cursor
from psycopg_pool import ConnectionPool

from .config import DATABASE_URL

# Pool sizing is tuned for a HIGH-LATENCY database.
#
# DATABASE_URL points at Postgres through an ngrok TCP tunnel: ~179 ms per
# connect and every query is a network round trip. The farmer endpoints are
# chatty by design - score_crop() alone runs 5 queries per crop, and
# /farmer/crop-recommendation scores up to 9 eligible crops, so one request can
# be 40+ sequential round trips while holding a connection the whole time.
#
# With the previous max_size=5, a burst (the browser retrying its TanStack
# Query calls after a backend restart) drained the pool and every later request
# died on `PoolTimeout: couldn't get a connection after 30.00 sec` -> HTTP 500.
#
#   min_size=4          pre-warm, because a cold connect costs ~179 ms
#   max_size=20         absorb a retry burst instead of timing out
#   timeout=10          fail fast; the frontend retries, a 30 s hang just
#                       occupies a worker and still ends in an error
#   max_idle=120        recycle aggressively - a tunnel silently drops idle
#                       connections, and a dead one surfaces as a 500
#   check=check_connection  ping before handing a connection out, so a
#                       tunnel reconnect costs one retry instead of a 500
#
# open=False: don't connect at import time (uvicorn's --reload subprocess
# re-imports this module before the app lifespan runs).
pool = ConnectionPool(
    conninfo=DATABASE_URL or "",
    open=False,
    min_size=4,
    max_size=20,
    timeout=10.0,
    max_idle=120.0,
    check=ConnectionPool.check_connection,
)


def get_cursor() -> Iterator[Cursor]:
    with pool.connection() as conn, conn.cursor() as cur:
        yield cur
