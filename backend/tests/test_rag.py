from __future__ import annotations

API = "/api/v1"


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_rag_query_requires_authentication(client):
    resp = client.post(f"{API}/rag/query", json={"mode": "ask", "question": "why?", "district_id": 1})
    assert resp.status_code == 401


def test_rag_explain_mode_grounds_in_real_market_data_and_flags_placeholder(client, farmer_token):
    resp = client.post(
        f"{API}/rag/query",
        headers=auth_header(farmer_token),
        json={"mode": "explain", "crop_id": 7, "district_id": 1, "computed_context": {"opportunity_pct": 84, "demand_gap": 36644.3}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "Tomato" in body["answer"]
    assert "Nashik" in body["answer"]
    assert "84%" in body["answer"]
    # fertilizer_recommendations for Tomato is seeded with is_verified=false
    assert body["used_placeholder_data"] is True


def test_rag_explain_mode_requires_crop_and_district(client, farmer_token):
    resp = client.post(f"{API}/rag/query", headers=auth_header(farmer_token), json={"mode": "explain", "crop_id": 7})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_rag_ask_mode_with_no_indexed_chunks_declines_rather_than_fabricates(client, farmer_token):
    resp = client.post(
        f"{API}/rag/query",
        headers=auth_header(farmer_token),
        json={"mode": "ask", "question": "Why is Urea demand rising in Nashik?", "district_id": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "don't have grounded information" in body["answer"]
    assert body["sources"] == []
    assert body["used_placeholder_data"] is False


def test_rag_ask_mode_requires_question(client, farmer_token):
    resp = client.post(f"{API}/rag/query", headers=auth_header(farmer_token), json={"mode": "ask", "district_id": 1})
    assert resp.status_code == 400


def test_rag_ask_mode_uses_retrieved_chunks_when_present(client, farmer_token, db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_chunks (source_id, chunk_index, chunk_text, state_id)
            VALUES (1, 0, 'Nashik Urea demand has risen due to expanded Kharif sowing.', 1)
            """,
        )

    resp = client.post(
        f"{API}/rag/query",
        headers=auth_header(farmer_token),
        json={"mode": "ask", "question": "Why is Urea demand rising in Nashik?", "district_id": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "Nashik Urea demand has risen" in body["answer"]
    assert body["sources"] and body["sources"][0]["source_id"] == 1
