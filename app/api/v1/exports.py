"""F-09. 이력·추적성 — CSV 내보내기.

- GET /api/v1/exports/weld-events.csv : 타점 이력 CSV 다운로드 (스트리밍)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.models.weld_event import JudgementStatus
from app.services.weld_event_service import stream_weld_events_csv

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get(
    "/weld-events.csv",
    summary="타점 이력 CSV 내보내기",
    response_class=StreamingResponse,
)
async def export_weld_events_csv(
    part_id: str | None = Query(default=None, description="부품 ID 필터."),
    point_id: str | None = Query(default=None, description="타점 ID 필터."),
    status: JudgementStatus | None = Query(
        default=None, description="판정 상태 필터(NORMAL/CAUTION/REJECT)."
    ),
    from_: datetime | None = Query(
        default=None,
        alias="from",
        description="시작 시각(inclusive, ISO 8601).",
    ),
    to: datetime | None = Query(
        default=None, description="종료 시각(inclusive, ISO 8601)."
    ),
):
    """필터 조건과 동일한 GET /weld-events 결과를 CSV로 다운로드."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"weld-events-{stamp}.csv"
    return StreamingResponse(
        stream_weld_events_csv(
            part_id=part_id,
            point_id=point_id,
            status=status,
            from_=from_,
            to=to,
        ),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
