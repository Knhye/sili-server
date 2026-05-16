"""F-02. 부품 마스터 관리 — REST 엔드포인트.

- GET    /api/v1/parts             : 목록 (필터: material_code, quality_class + skip/limit)
- POST   /api/v1/parts              : 등록 (part_id 중복 시 409)
- GET    /api/v1/parts/{part_id}    : 단건 조회
- PATCH  /api/v1/parts/{part_id}    : 부분 갱신
- DELETE /api/v1/parts/{part_id}    : 삭제
"""

from fastapi import APIRouter, Query, status

from app.core.response import ApiResponse, success_response
from app.models.part import MaterialCode, QualityClass
from app.schemas.part import PartCreate, PartRead, PartUpdate
from app.services.part_service import (
    create_part,
    delete_part,
    get_part,
    list_parts,
    update_part,
)

router = APIRouter(prefix="/parts", tags=["parts"])


@router.get(
    "",
    response_model=ApiResponse[list[PartRead]],
    summary="부품 마스터 목록 조회",
)
async def list_parts_endpoint(
    material_code: MaterialCode | None = Query(default=None, description="재질 코드 필터."),
    quality_class: QualityClass | None = Query(default=None, description="품질 등급 필터."),
    skip: int = Query(default=0, ge=0, description="건너뛸 건수."),
    limit: int = Query(default=50, ge=1, le=200, description="최대 반환 건수."),
):
    docs = await list_parts(
        material_code=material_code,
        quality_class=quality_class,
        skip=skip,
        limit=limit,
    )
    return success_response(
        data=[PartRead.from_document(d).model_dump(mode="json") for d in docs]
    )


@router.post(
    "",
    response_model=ApiResponse[PartRead],
    status_code=status.HTTP_201_CREATED,
    summary="부품 마스터 등록",
)
async def create_part_endpoint(payload: PartCreate):
    part = await create_part(payload.model_dump(mode="json"))
    return success_response(
        data=PartRead.from_document(part).model_dump(mode="json"),
        message="Created",
        code=201,
    )


@router.get(
    "/{part_id}",
    response_model=ApiResponse[PartRead],
    summary="부품 마스터 단건 조회",
)
async def get_part_endpoint(part_id: str):
    part = await get_part(part_id)
    return success_response(
        data=PartRead.from_document(part).model_dump(mode="json")
    )


@router.patch(
    "/{part_id}",
    response_model=ApiResponse[PartRead],
    summary="부품 마스터 부분 갱신",
)
async def patch_part_endpoint(part_id: str, payload: PartUpdate):
    updates = payload.model_dump(exclude_unset=True, mode="json")
    part = await update_part(part_id, updates)
    return success_response(
        data=PartRead.from_document(part).model_dump(mode="json"),
        message="Updated",
    )


@router.delete(
    "/{part_id}",
    response_model=ApiResponse[dict],
    summary="부품 마스터 삭제",
)
async def delete_part_endpoint(part_id: str):
    await delete_part(part_id)
    return success_response(
        data={"part_id": part_id},
        message="Deleted",
    )
