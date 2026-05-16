"""F-02. 부품 마스터 (Part Master) — Beanie Document + 임베드 모델.

차종·부품별 재질·두께·품질등급·전극형상을 사전 등록한다.
부품 바코드 스캔(또는 F-01 의 `part_id`) 으로 단건 조회되어, 판정 엔진이
config 의 두께 한계/재질 보정 계수/등급별 허용 편차/전극 형상 규칙을 끌어
이상 점수를 계산한다.

`weld_points` 는 한 부품에 속한 타점 정의로 항상 같이 조회되므로 임베드.
좌표(`position_x/y`) 는 F-11 (최소 피치/Lap 체크) 활성화 시점부터 필수가
되지만 v1 에서는 선택값으로 둔다.
"""

from datetime import datetime, timezone
from enum import Enum

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel


class MaterialCode(str, Enum):
    """판재 재질 코드. 미등록 재질 투입 시 판정 엔진이 🔴 재검권장 강제 격상."""

    MILD = "MILD"
    HSLA = "HSLA"
    DP600 = "DP600"
    DP980 = "DP980"
    UHSS = "UHSS"
    GA = "GA"
    GI = "GI"


class QualityClass(str, Enum):
    """품질 등급. config 의 `quality_class_tolerance` 키와 일치해야 한다."""

    A = "A"
    B = "B"
    C = "C"


class ElectrodeShape(str, Enum):
    """전극 형상 코드. 판두께 기준 권장값과 다르면 🟡 주의 강제 격상."""

    C_TYPE = "C-TYPE"
    R_TYPE = "R-TYPE"


class WeldPoint(BaseModel):
    """부품 내 개별 타점 정의 (임베드)."""

    point_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="부품 내 타점 식별자 (예: 'P-001'). 부품 내에서 unique 권장.",
    )
    position_x: float | None = Field(
        default=None,
        description="타점 X 좌표 (mm). F-11 최소 피치 체크에 사용, v1 보류 항목.",
    )
    position_y: float | None = Field(
        default=None,
        description="타점 Y 좌표 (mm). F-11 최소 피치 체크에 사용, v1 보류 항목.",
    )
    sequence_no: int = Field(
        ...,
        ge=1,
        description="타점 순번 (1부터, 작업 순서 기준).",
    )


class Part(Document):
    """부품 마스터 도큐먼트 (`parts` 컬렉션).

    `part_id` 가 도메인 식별자이며 unique 인덱스로 보호된다. `_id` 는 ObjectId
    기본값을 그대로 사용한다.
    """

    part_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="부품 마스터 식별자 (바코드/도면 번호). 예: 'BODY-0042'.",
    )
    material_code: MaterialCode = Field(
        ..., description="판재 재질 코드 (config.material_profiles 키와 일치)."
    )
    t1: float = Field(
        ..., gt=0, description="판재 1 두께 (mm). > 0."
    )
    t2: float = Field(
        ..., gt=0, description="판재 2 두께 (mm). > 0. 이종 두께 허용."
    )
    quality_class: QualityClass = Field(
        ...,
        description=(
            "품질 등급 (A/B/C). 판정 엔진이 얇은 쪽 두께(3.2mm 기준)에 따라 "
            "`config.quality_class_tolerance[등급].thin/thick` 을 선택한다."
        ),
    )
    electrode_shape: ElectrodeShape = Field(
        ...,
        description=(
            "장착 전극 형상 코드 (C-TYPE/R-TYPE). `config.electrode_shape_rule` "
            "의 권장값과 불일치 시 🟡 주의 격상."
        ),
    )
    weld_points: list[WeldPoint] = Field(
        default_factory=list,
        description="부품에 속한 타점 정의 목록 (임베드). 없으면 빈 배열.",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="생성 시각 (UTC).",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="마지막 수정 시각 (UTC). PATCH 시 자동 갱신.",
    )

    class Settings:
        name = "parts"
        indexes = [
            IndexModel("part_id", unique=True),
            IndexModel("material_code"),
            IndexModel("quality_class"),
        ]
