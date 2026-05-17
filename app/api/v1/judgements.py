"""F-09. 이력·추적성 — 판정 결과 상세 조회.

- GET /api/v1/judgements/{event_id} : 단건 판정 상세 (event_id 기준)
"""

from fastapi import APIRouter

from app.core.exceptions import AppException
from app.core.response import ApiResponse, success_response
from app.schemas.judgement import JudgementDetailRead
from app.services.weld_event_service import get_weld_event

router = APIRouter(prefix="/judgements", tags=["judgements"])


@router.get(
    "/{event_id}",
    response_model=ApiResponse[JudgementDetailRead],
    summary="판정 결과 상세 조회",
)
async def get_judgement_endpoint(event_id: str):
    event = await get_weld_event(event_id)
    if event.judgement is None:
        raise AppException(
            message=f"판정 결과가 없습니다: event_id={event_id}",
            code=404,
        )
    return success_response(
        data=JudgementDetailRead.from_event(event).model_dump(mode="json")
    )
