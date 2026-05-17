"""F-01 공정 데이터 수집 + F-09 이력 조회 — REST 엔드포인트.

- POST /api/v1/weld-events           : 타점 데이터 수신 + 즉시 판정 (PLC)
- GET  /api/v1/weld-events           : 타점 이력 조회 (필터·페이지네이션)
"""

from datetime import datetime

from fastapi import APIRouter, Query, status

from app.core.response import ApiResponse, success_response
from app.models.weld_event import JudgementStatus
from app.schemas.weld_event import WeldEventCreate, WeldEventRead
from app.services.weld_event_service import ingest_weld_event, list_weld_events

router = APIRouter(prefix="/weld-events", tags=["weld-events"])


@router.post(
    "",
    response_model=ApiResponse[WeldEventRead],
    status_code=status.HTTP_201_CREATED,
    summary="타점 데이터 수신 + 즉시 판정 (PLC)",
)
async def post_weld_event(payload: WeldEventCreate):
    event = await ingest_weld_event(payload.model_dump(mode="json"))
    return success_response(
        data=WeldEventRead.from_document(event).model_dump(mode="json"),
        message="OK",
        code=201,
    )


@router.get(
    "",
    response_model=ApiResponse[list[WeldEventRead]],
    summary="타점 이력 조회 (필터·페이지네이션)",
)
async def list_weld_events_endpoint(
    part_id: str | None = Query(default=None, description="부품 ID 필터."),
    point_id: str | None = Query(default=None, description="타점 ID 필터."),
    status_: JudgementStatus | None = Query(
        default=None,
        alias="status",
        description="판정 상태 필터(NORMAL/CAUTION/REJECT).",
    ),
    from_: datetime | None = Query(
        default=None,
        alias="from",
        description="시작 시각(inclusive, ISO 8601).",
    ),
    to: datetime | None = Query(
        default=None, description="종료 시각(inclusive, ISO 8601)."
    ),
    skip: int = Query(default=0, ge=0, description="건너뛸 건수."),
    limit: int = Query(
        default=50, ge=1, le=200, description="최대 반환 건수."
    ),
):
    docs = await list_weld_events(
        part_id=part_id,
        point_id=point_id,
        status=status_,
        from_=from_,
        to=to,
        skip=skip,
        limit=limit,
    )
    return success_response(
        data=[WeldEventRead.from_document(d).model_dump(mode="json") for d in docs]
    )
