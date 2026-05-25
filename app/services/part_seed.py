"""부팅 시 개발/테스트용 부품 마스터 시드.

- BODY-0042: weld_points 에 더미 "string" point_id 가 있으면 실제 값으로 교체.
- BODY-3294: weld_points 가 비어 있으면 실제 타점 목록을 추가.

멱등(idempotent): 정상 데이터가 이미 있으면 no-op.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models.part import (
    ElectrodeShape,
    MaterialCode,
    Part,
    QualityClass,
    WeldPoint,
)

logger = logging.getLogger(__name__)

_SEED_PARTS: list[dict] = [
    {
        "part_id": "BODY-0042",
        "material_code": MaterialCode.MILD,
        "t1": 0.8,
        "t2": 1.2,
        "quality_class": QualityClass.B,
        "electrode_shape": ElectrodeShape.C_TYPE,
        "weld_points": [
            WeldPoint(point_id="P-001", sequence_no=1),
            WeldPoint(point_id="P-002", sequence_no=2),
            WeldPoint(point_id="P-003", sequence_no=3),
            WeldPoint(point_id="P-004", sequence_no=4),
        ],
    },
    {
        "part_id": "BODY-3294",
        "material_code": MaterialCode.MILD,
        "t1": 1.0,
        "t2": 1.6,
        "quality_class": QualityClass.B,
        "electrode_shape": ElectrodeShape.C_TYPE,
        "weld_points": [
            WeldPoint(point_id="P-001", sequence_no=1),
            WeldPoint(point_id="P-002", sequence_no=2),
            WeldPoint(point_id="P-003", sequence_no=3),
        ],
    },
]


def _needs_fix(part: Part) -> bool:
    """weld_points 가 비어있거나 더미값("string")을 포함하면 True."""
    if not part.weld_points:
        return True
    return any(wp.point_id == "string" for wp in part.weld_points)


async def seed_dev_parts() -> None:
    for spec in _SEED_PARTS:
        part_id: str = spec["part_id"]
        weld_points: list[WeldPoint] = spec["weld_points"]
        existing = await Part.find_one(Part.part_id == part_id)

        if existing is None:
            await Part(**spec).insert()
            logger.info(
                "part seeded (part_id=%s, points=%d)", part_id, len(weld_points)
            )
            continue

        if _needs_fix(existing):
            existing.weld_points = weld_points
            existing.updated_at = datetime.now(timezone.utc)
            await existing.save()
            logger.info(
                "part weld_points fixed (part_id=%s, points=%d)",
                part_id,
                len(weld_points),
            )
        else:
            logger.info(
                "part seed skipped: weld_points already set (part_id=%s)", part_id
            )
