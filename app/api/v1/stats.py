"""대시보드 KPI — REST 엔드포인트.

- GET /api/v1/stats/shift : 교대(shift) 합격률 + 시간당 생산
"""

from fastapi import APIRouter, Query

from app.core.response import ApiResponse, success_response
from app.services.stats_service import get_shift_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get(
    "/shift",
    response_model=ApiResponse[dict],
    summary="교대 합격률 + 시간당 생산 KPI",
)
async def get_shift_stats_endpoint(
    hours: int = Query(
        default=8, ge=1, le=24, description="윈도우 시간 길이 (기본 8h)."
    ),
    line_id: str | None = Query(
        default=None, description="라인 필터. 미지정 시 전체 라인 합산."
    ),
):
    data = await get_shift_stats(hours=hours, line_id=line_id)
    return success_response(data=data)
