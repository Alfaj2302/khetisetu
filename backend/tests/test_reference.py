"""Reference/dropdown endpoints.

None of these implement pagination or free-text search — they're small,
fixed lookup tables (<=29 rows) returned in full, ordered by id. The only
real "provision" here is the optional equality filter on /districts
(state_id) and /products (fertilizer_type), tested below.
"""

from __future__ import annotations

API = "/api/v1"


def _ids(body: list[dict]) -> list[int]:
    return [row["id"] for row in body]


def test_list_states(client):
    resp = client.get(f"{API}/states")
    assert resp.status_code == 200
    body = resp.json()
    assert any(s["name"] == "Maharashtra" and s["state_code"] == "MH" for s in body)
    assert _ids(body) == sorted(_ids(body))  # ordered by id


def test_list_districts_unfiltered_returns_all_seven(client):
    resp = client.get(f"{API}/districts")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 7
    assert {d["name"] for d in body} >= {"Nashik", "Pune", "Nagpur"}
    assert _ids(body) == sorted(_ids(body))


def test_list_districts_filtered_by_state_id(client):
    all_districts = client.get(f"{API}/districts").json()
    filtered = client.get(f"{API}/districts", params={"state_id": 1}).json()
    assert filtered == all_districts  # every seeded district belongs to state_id 1

    empty = client.get(f"{API}/districts", params={"state_id": 999}).json()
    assert empty == []


def test_list_crops(client):
    resp = client.get(f"{API}/crops")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 13
    assert any(c["name"] == "Tomato" for c in body)
    assert _ids(body) == sorted(_ids(body))


def test_list_seasons(client):
    resp = client.get(f"{API}/seasons")
    assert resp.status_code == 200
    body = resp.json()
    names = {s["name"] for s in body}
    assert names == {"Kharif", "Rabi", "Zaid"}


def test_list_products_unfiltered(client):
    resp = client.get(f"{API}/products")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 29
    assert _ids(body) == sorted(_ids(body))


def test_list_products_filtered_by_fertilizer_type(client):
    resp = client.get(f"{API}/products", params={"fertilizer_type": "Nitrogen"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    assert all(p["fertilizer_type"] == "Nitrogen" for p in body)
    assert any(p["product_name"] == "Urea" for p in body)


def test_list_products_filtered_by_unknown_fertilizer_type_is_empty(client):
    resp = client.get(f"{API}/products", params={"fertilizer_type": "NoSuchType"})
    assert resp.status_code == 200
    assert resp.json() == []
