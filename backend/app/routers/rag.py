from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import Cursor

from ..db import get_cursor
from ..deps import get_current_user
from ..errors import ApiError
from ..schemas import RagQueryRequest, RagQueryResponse, RagSourceRef
from ..services import rag as rag_service

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(get_current_user)])


@router.post("/query", response_model=RagQueryResponse)
def rag_query(payload: RagQueryRequest, cur: Cursor = Depends(get_cursor)) -> RagQueryResponse:
    if payload.mode == "explain":
        if payload.crop_id is None or payload.district_id is None:
            raise ApiError(400, "VALIDATION_ERROR", "explain mode requires crop_id and district_id")
        answer, sources, used_placeholder_data = rag_service.answer_explain(
            cur,
            crop_id=payload.crop_id,
            district_id=payload.district_id,
            computed_context=payload.computed_context,
        )
    else:
        if not payload.question:
            raise ApiError(400, "VALIDATION_ERROR", "ask mode requires question")
        answer, sources, used_placeholder_data = rag_service.answer_ask(
            cur,
            question=payload.question,
            district_id=payload.district_id,
        )

    return RagQueryResponse(
        answer=answer,
        sources=[RagSourceRef(**s) for s in sources],
        used_placeholder_data=used_placeholder_data,
    )
