from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from psycopg import Cursor

from ..db import get_cursor
from ..schemas import CropOut, DistrictOut, ProductOut, SeasonOut, StateOut

router = APIRouter(tags=["reference"])


@router.get("/states", response_model=list[StateOut])
def list_states(cur: Cursor = Depends(get_cursor)) -> list[StateOut]:
    cur.execute("SELECT id, name, state_code FROM states ORDER BY id")
    return [StateOut(id=r[0], name=r[1], state_code=r[2]) for r in cur.fetchall()]


@router.get("/districts", response_model=list[DistrictOut])
def list_districts(
    state_id: int | None = Query(default=None),
    cur: Cursor = Depends(get_cursor),
) -> list[DistrictOut]:
    if state_id is not None:
        cur.execute(
            "SELECT id, state_id, name, latitude, longitude, also_known_as "
            "FROM districts WHERE state_id = %s ORDER BY id",
            (state_id,),
        )
    else:
        cur.execute("SELECT id, state_id, name, latitude, longitude, also_known_as FROM districts ORDER BY id")
    return [
        DistrictOut(
            id=r[0],
            state_id=r[1],
            name=r[2],
            latitude=float(r[3]) if r[3] is not None else None,
            longitude=float(r[4]) if r[4] is not None else None,
            also_known_as=r[5],
        )
        for r in cur.fetchall()
    ]


@router.get("/crops", response_model=list[CropOut])
def list_crops(cur: Cursor = Depends(get_cursor)) -> list[CropOut]:
    cur.execute("SELECT id, name, scientific_name, crop_category FROM crops ORDER BY id")
    return [CropOut(id=r[0], name=r[1], scientific_name=r[2], crop_category=r[3]) for r in cur.fetchall()]


@router.get("/seasons", response_model=list[SeasonOut])
def list_seasons(cur: Cursor = Depends(get_cursor)) -> list[SeasonOut]:
    cur.execute("SELECT id, name, start_month, end_month FROM seasons ORDER BY id")
    return [SeasonOut(id=r[0], name=r[1], start_month=r[2], end_month=r[3]) for r in cur.fetchall()]


@router.get("/products", response_model=list[ProductOut])
def list_products(
    fertilizer_type: str | None = Query(default=None),
    cur: Cursor = Depends(get_cursor),
) -> list[ProductOut]:
    if fertilizer_type:
        cur.execute(
            "SELECT id, product_name, product_type, fertilizer_type "
            "FROM products WHERE fertilizer_type = %s ORDER BY id",
            (fertilizer_type,),
        )
    else:
        cur.execute("SELECT id, product_name, product_type, fertilizer_type FROM products ORDER BY id")
    return [ProductOut(id=r[0], product_name=r[1], product_type=r[2], fertilizer_type=r[3]) for r in cur.fetchall()]
