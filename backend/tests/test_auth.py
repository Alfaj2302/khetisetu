from __future__ import annotations

from app.security import create_access_token, decode_access_token

API = "/api/v1"


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_success(client):
    resp = client.post(
        f"{API}/auth/register",
        json={
            "name": "Test Farmer",
            "role": "FARMER",
            "email": "auth.success@example.com",
            "password": "password123",
            "state_id": 1,
            "district_id": 1,
            "phone": "9999999999",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "FARMER"
    assert body["email"] == "auth.success@example.com"
    assert isinstance(body["id"], int)


def test_register_duplicate_email_is_rejected(client):
    payload = {"role": "FARMER", "email": "auth.dup@example.com", "password": "password123"}
    first = client.post(f"{API}/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post(f"{API}/auth/register", json=payload)
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_rejects_unknown_role(client):
    resp = client.post(
        f"{API}/auth/register",
        json={"role": "SUPERADMIN", "email": "auth.badrole@example.com", "password": "password123"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_rejects_missing_required_field(client):
    resp = client.post(f"{API}/auth/register", json={"email": "auth.missing@example.com", "password": "x"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_success_and_token_claims(client):
    register = client.post(
        f"{API}/auth/register",
        json={"role": "AGRI_BUSINESS", "email": "auth.login@example.com", "password": "password123", "district_id": 2},
    )
    assert register.status_code == 201
    user_id = register.json()["id"]

    login = client.post(f"{API}/auth/login", json={"email": "auth.login@example.com", "password": "password123"})
    assert login.status_code == 200
    body = login.json()
    assert body["user"] == {"id": user_id, "role": "AGRI_BUSINESS", "district_id": 2}

    claims = decode_access_token(body["token"])
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "AGRI_BUSINESS"
    assert claims["district_id"] == 2


def test_login_wrong_password_is_unauthorized(client):
    client.post(f"{API}/auth/register", json={"role": "FARMER", "email": "auth.wrongpw@example.com", "password": "correct123"})
    resp = client.post(f"{API}/auth/login", json={"email": "auth.wrongpw@example.com", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_unknown_email_is_unauthorized(client):
    resp = client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_stale_user_token_is_401_not_500_on_optional_auth_route(client):
    # A validly-signed token for a user id that doesn't exist (e.g. the
    # account was deleted after the token was issued) must fail cleanly,
    # even on a route where auth is optional.
    token = create_access_token(user_id=999_999_999, role="FARMER", district_id=1)
    resp = client.post(
        f"{API}/farmer/crop-recommendation",
        headers=auth_header(token),
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 6},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_stale_user_token_is_401_not_500_on_required_auth_route(client):
    token = create_access_token(user_id=999_999_999, role="AGRI_BUSINESS", district_id=None)
    resp = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 1, "season_id": 1, "year": 2026},
        headers=auth_header(token),
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"
