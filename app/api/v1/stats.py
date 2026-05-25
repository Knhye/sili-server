"""대시보드 KPI — REST 엔드포인트.

- GET /api/v1/stats/shift : 교대(shift) 합격률 + 시간당 생산
"""

from fastapi import APIRouter, Query

from app.core.response import ApiResponse, success_response
from app.services.stats_service import get_shift_stats, get_user_performance_stats

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


@router.get(
    "/user-performance",
    response_model=ApiResponse[list],
    summary="검사자별 퍼포먼스 통계 (재검 건수·감시 타점·합격률)",
)
async def get_user_performance_endpoint(
    inspector_id: str | None = Query(
        default=None, description="검사자 ID 필터. 미지정 시 전체 검사자."
    ),
    hours: int | None = Query(
        default=None, ge=1, le=720, description="윈도우 시간 길이. 미지정 시 전체 기간."
    ),
):
    data = await get_user_performance_stats(inspector_id=inspector_id, hours=hours)
    return success_response(data=data)
