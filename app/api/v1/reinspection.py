"""F-06. 재검 큐 관리 — REST 엔드포인트.

- GET  /api/v1/reinspection                    : 큐 목록 (필터: status, part_id)
- GET  /api/v1/reinspection/{queue_id}         : 큐 단건 조회
- POST /api/v1/reinspection/{queue_id}/result  : 재검 결과 등록 → CLOSED 전이
"""

from fastapi import APIRouter, Query, status

from app.core.response import ApiResponse, success_response
from app.models.reinspection import ReinspectionStatus
from app.schemas.reinspection import ReinspectionRead, ReinspectionResultCreate
from app.services.reinspection_service import (
    get_queue,
    list_queues,
    submit_result,
)

router = APIRouter(prefix="/reinspection", tags=["reinspection"])


@router.get(
    "",
    response_model=ApiResponse[list[ReinspectionRead]],
    summary="재검 큐 목록 조회",
)
async def list_queues_endpoint(
    status_: ReinspectionStatus | None = Query(
        default=None,
        alias="status",
        description="큐 상태 필터. 미지정 시 전체.",
    ),
    part_id: str | None = Query(default=None, description="부품 ID 필터."),
    skip: int = Query(default=0, ge=0, description="건너뛸 건수."),
    limit: int = Query(default=50, ge=1, le=200, description="최대 반환 건수."),
):
    docs = await list_queues(
        status=status_, part_id=part_id, skip=skip, limit=limit
    )
    return success_response(
        data=[ReinspectionRead.from_document(d).model_dump(mode="json") for d in docs]
    )


@router.get(
    "/{queue_id}",
    response_model=ApiResponse[ReinspectionRead],
    summary="재검 큐 단건 조회",
)
async def get_queue_endpoint(queue_id: str):
    queue = await get_queue(queue_id)
    return success_response(
        data=ReinspectionRead.from_document(queue).model_dump(mode="json")
    )


@router.post(
    "/{queue_id}/result",
    response_model=ApiResponse[ReinspectionRead],
    status_code=status.HTTP_201_CREATED,
    summary="재검 결과 등록 (작업자) → CLOSED",
)
async def submit_result_endpoint(queue_id: str, payload: ReinspectionResultCreate):
    queue = await submit_result(queue_id, payload.model_dump(mode="json"))
    return success_response(
        data=ReinspectionRead.from_document(queue).model_dump(mode="json"),
        message="Closed",
        code=201,
    )
