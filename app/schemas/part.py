"""F-02. 부품 마스터 관리 — Pydantic DTO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.part import (
    ElectrodeShape,
    MaterialCode,
    QualityClass,
    WeldPoint,
)


class PartCreate(BaseModel):
    """`POST /api/v1/parts` 요청 본문."""

    part_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="부품 마스터 식별자. 중복 시 409 반환.",
        examples=["BODY-0042"],
    )
    material_code: MaterialCode = Field(
        ..., description="판재 재질 코드 (Enum 검증)."
    )
    t1: float = Field(..., gt=0, description="판재 1 두께 (mm).", examples=[0.8])
    t2: float = Field(..., gt=0, description="판재 2 두께 (mm).", examples=[1.2])
    quality_class: QualityClass = Field(..., description="품질 등급 (A/B/C).")
    electrode_shape: ElectrodeShape = Field(
        ..., description="장착 전극 형상 코드 (C-TYPE/R-TYPE)."
    )
    weld_points: list[WeldPoint] = Field(
        default_factory=list,
        description="부품에 속한 타점 정의. 없으면 빈 배열.",
    )


class PartUpdate(BaseModel):
    """`PATCH /api/v1/parts/{part_id}` 요청 본문 (부분 갱신).

    제공된 키만 갱신된다. `part_id` 자체는 식별자이므로 변경 불가.
    `weld_points` 는 dict 필드와 동일하게 **전체 교체** 방식.
    """

    material_code: MaterialCode | None = Field(default=None, description="판재 재질 코드.")
    t1: float | None = Field(default=None, gt=0, description="판재 1 두께 (mm).")
    t2: float | None = Field(default=None, gt=0, description="판재 2 두께 (mm).")
    quality_class: QualityClass | None = Field(default=None, description="품질 등급.")
    electrode_shape: ElectrodeShape | None = Field(
        default=None, description="장착 전극 형상 코드."
    )
    weld_points: list[WeldPoint] | None = Field(
        default=None, description="타점 정의 전체 교체."
    )


class PartRead(BaseModel):
    """`GET /api/v1/parts(/{part_id})` 응답 본문."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="MongoDB ObjectId(문자열).")
    part_id: str = Field(..., description="부품 마스터 식별자.")
    material_code: MaterialCode
    t1: float
    t2: float
    quality_class: QualityClass
    electrode_shape: ElectrodeShape
    weld_points: list[WeldPoint] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, doc) -> "PartRead":
        return cls(
            id=str(doc.id),
            part_id=doc.part_id,
            material_code=doc.material_code,
            t1=doc.t1,
            t2=doc.t2,
            quality_class=doc.quality_class,
            electrode_shape=doc.electrode_shape,
            weld_points=doc.weld_points,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
