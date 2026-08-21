from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Cursor

from .db import get_cursor
from .errors import ApiError
from .security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    role: str
    district_id: int | None


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    cur: Cursor = Depends(get_cursor),
) -> CurrentUser | None:
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as error:
        raise ApiError(401, "UNAUTHORIZED", "Invalid or expired token") from error

    user_id = int(payload["sub"])
    # The token's claims are trusted for role/district_id, but the user row
    # itself might be gone since the token was issued (deleted account) —
    # without this check that surfaces as a raw ForeignKeyViolation/500 the
    # first time the request tries to write a row referencing user_id.
    cur.execute("SELECT 1 FROM users WHERE id = %s", (user_id,))
    if cur.fetchone() is None:
        raise ApiError(401, "UNAUTHORIZED", "Token refers to a user that no longer exists")

    return CurrentUser(
        id=user_id,
        role=payload["role"],
        district_id=payload.get("district_id"),
    )


def get_current_user(user: CurrentUser | None = Depends(get_current_user_optional)) -> CurrentUser:
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Missing or invalid bearer token")
    return user


def require_roles(*roles: str):
    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise ApiError(403, "FORBIDDEN", f"Role '{user.role}' cannot access this endpoint")
        return user

    return _check
