"""F-02. 부품 마스터 관리 — 서비스 레이어.

CRUD + 도메인 식별자(`part_id`) 기반 단건 조회. `part_id` 유니크 제약은
DB 인덱스(`Part.Settings.indexes`) 로 보호되며, 중복 INSERT 는
`AppException(409)` 로 매핑된다.
"""

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.exceptions import AppException
from app.models.part import MaterialCode, Part, QualityClass


async def create_part(payload: dict[str, Any]) -> Part:
    part = Part(**payload)
    try:
        await part.insert()
    except DuplicateKeyError:
        raise AppException(
            message=f"이미 등록된 부품입니다: part_id={payload.get('part_id')}",
            code=409,
        )
    return part


async def get_part(part_id: str) -> Part:
    part = await Part.find_one(Part.part_id == part_id)
    if part is None:
        raise AppException(
            message=f"부품을 찾을 수 없습니다: part_id={part_id}",
            code=404,
        )
    return part


async def list_parts(
    *,
    material_code: MaterialCode | None = None,
    quality_class: QualityClass | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Part]:
    """선택적 필터 + 페이지네이션. 최신 생성순 정렬."""
    query: dict[str, Any] = {}
    if material_code is not None:
        query["material_code"] = material_code.value
    if quality_class is not None:
        query["quality_class"] = quality_class.value

    return (
        await Part.find(query)
        .sort(-Part.created_at)
        .skip(skip)
        .limit(limit)
        .to_list()
    )


async def update_part(part_id: str, updates: dict[str, Any]) -> Part:
    """제공된 필드만 갱신. 변경 없으면 `updated_at` 만 유지."""
    part = await get_part(part_id)

    changed = False
    for key, value in updates.items():
        if getattr(part, key) != value:
            setattr(part, key, value)
            changed = True

    if changed:
        part.updated_at = datetime.now(timezone.utc)
        await part.save()
    return part


async def delete_part(part_id: str) -> None:
    part = await get_part(part_id)
    await part.delete()
