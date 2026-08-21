"""Shared test fixtures.

Every test runs inside one Postgres transaction on a dedicated connection
that's rolled back at teardown — writes made via the API during a test
(register, crop-intent, crop-recommendation, ...) never actually persist,
so the suite is safe to run repeatedly against the same seeded dev database
(the one `db/sync.py` sets up) without accumulating junk rows or hitting
duplicate-email errors on a second run.

Requires `src/backend/.env` pointing at a Postgres instance that already
has the schema + seed data applied (`python src/backend/db/sync.py`).
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

_email_counter = itertools.count(1)

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DATABASE_URL  # noqa: E402
from app.db import get_cursor  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token  # noqa: E402


@pytest.fixture()
def db_conn():
    if not DATABASE_URL:
        pytest.fail("DATABASE_URL is not set — copy src/backend/.env.example to .env first")
    conn = psycopg.connect(DATABASE_URL)
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture()
def client(db_conn):
    def _override_get_cursor():
        with db_conn.cursor() as cur:
            yield cur

    app.dependency_overrides[get_cursor] = _override_get_cursor
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _insert_test_user(db_conn, *, role: str, district_id: int | None) -> int:
    # farmer_crop_intent.user_id (and users.id in general) is a real FK —
    # a token minted for an id that was never inserted fails downstream
    # with a raw ForeignKeyViolation, not a clean API error. So fixtures
    # back every test token with an actual row, in the same per-test
    # transaction that gets rolled back at teardown.
    email = f"fixture-{role.lower()}-{next(_email_counter)}@example.com"
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (role, email, district_id) VALUES (%s, %s, %s) RETURNING id",
            (role, email, district_id),
        )
        return cur.fetchone()[0]


@pytest.fixture()
def farmer_token(db_conn) -> str:
    user_id = _insert_test_user(db_conn, role="FARMER", district_id=1)
    return create_access_token(user_id=user_id, role="FARMER", district_id=1)


@pytest.fixture()
def business_token(db_conn) -> str:
    user_id = _insert_test_user(db_conn, role="AGRI_BUSINESS", district_id=None)
    return create_access_token(user_id=user_id, role="AGRI_BUSINESS", district_id=None)


@pytest.fixture()
def admin_token(db_conn) -> str:
    user_id = _insert_test_user(db_conn, role="ADMIN", district_id=None)
    return create_access_token(user_id=user_id, role="ADMIN", district_id=None)
