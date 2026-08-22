from __future__ import annotations

from fastapi import APIRouter, Depends
from psycopg import Cursor

from ..db import get_cursor
from ..deps import get_current_user
from ..errors import ApiError
from ..schemas import RagQueryRequest, RagQueryResponse, RagStatusResponse
from ..services import rag as rag_service

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(get_current_user)])


@router.post("/query", response_model=RagQueryResponse)
def rag_query(payload: RagQueryRequest, cur: Cursor = Depends(get_cursor)) -> RagQueryResponse:
    if payload.mode == "explain":
        if payload.crop_id is None or payload.district_id is None:
            raise ApiError(400, "VALIDATION_ERROR", "explain mode requires crop_id and district_id")
        result = rag_service.answer_explain(
            cur,
            crop_id=payload.crop_id,
            district_id=payload.district_id,
            computed_context=payload.computed_context,
        )
    else:
        if not payload.question:
            raise ApiError(400, "VALIDATION_ERROR", "ask mode requires question")
        result = rag_service.answer_ask(
            cur,
            question=payload.question,
            district_id=payload.district_id,
        )

    # The dataclass field names are the response field names on purpose - one
    # place to add a field instead of three.
    return RagQueryResponse(**result.as_dict())


@router.get("/status", response_model=RagStatusResponse)
def rag_status(cur: Cursor = Depends(get_cursor)) -> RagStatusResponse:
    """Whether retrieval and generation are actually live.

    Without this, "the answer was thin" has three indistinguishable causes: no
    documents ingested, no embeddings key, no generation key.
    """
    return RagStatusResponse(**rag_service.status(cur))
