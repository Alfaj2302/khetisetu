from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends
from psycopg import Cursor

from ..db import get_cursor
from ..errors import ApiError
from ..schemas import LoginRequest, LoginResponse, LoginUser, RegisterRequest, RegisterResponse
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterRequest, cur: Cursor = Depends(get_cursor)) -> RegisterResponse:
    password_hash = hash_password(payload.password)
    try:
        cur.execute(
            """
            INSERT INTO users (name, role, email, password_hash, state_id, district_id, phone)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, name, role, email
            """,
            (
                payload.name,
                payload.role,
                payload.email,
                password_hash,
                payload.state_id,
                payload.district_id,
                payload.phone,
            ),
        )
    except psycopg.errors.UniqueViolation as error:
        raise ApiError(400, "VALIDATION_ERROR", "email is already registered") from error
    row = cur.fetchone()
    return RegisterResponse(id=row[0], name=row[1], role=row[2], email=row[3])


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, cur: Cursor = Depends(get_cursor)) -> LoginResponse:
    cur.execute(
        "SELECT id, role, district_id, password_hash FROM users WHERE email = %s",
        (payload.email,),
    )
    row = cur.fetchone()
    if row is None or row[3] is None or not verify_password(payload.password, row[3]):
        raise ApiError(401, "UNAUTHORIZED", "Invalid email or password")
    user_id, role, district_id, _ = row
    token = create_access_token(user_id=user_id, role=role, district_id=district_id)
    return LoginResponse(token=token, user=LoginUser(id=user_id, role=role, district_id=district_id))
