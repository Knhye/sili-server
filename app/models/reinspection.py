"""F-06. 재검 큐 관리 — Beanie Document + 임베드 모델.

F-05 판정이 🔴 REJECT 거나 F-04 강제 격상(🟡 CAUTION 포함) 인 경우
재검 큐에 자동 적재된다. 작업자는 큐를 조회해 실제 불량 여부를 입력하고,
이 결과는 향후 F-08 학습 환류 입력으로도 쓰인다 (docs F-06 / F-08 절).

큐 단위 정책 — **1 트리거 이벤트 = 1 큐**
  - 동일 부품의 다른 타점이 또 트리거되어도 새 큐가 INSERT 된다.
  - `event_ids` 는 항상 길이 1 (docs 스키마 호환을 위해 list 유지).
  - 같은 부품의 다중 큐 그루핑은 클라이언트(작업자 UI) 가 `part_id` 기준
    으로 처리한다 → 동시성 레이스/혼합 사유 누락/재투입 묶음 위험이
    구조적으로 사라진다.
"""

from datetime import datetime, timezone
from enum import Enum

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import IndexModel


class ReinspectionStatus(str, Enum):
    """재검 큐 상태 (docs F-06 표)."""

    PENDING = "PENDING"        # 큐 등록 직후, 작업자 미배정
    INSPECTING = "INSPECTING"  # 작업자가 검사 시작 (선택적 전이)
    CLOSED = "CLOSED"          # 재검 결과 등록 완료


class ReinspectionReason(str, Enum):
    """재검 큐 등록 사유.

    `ForcedReason` 값과 문자열이 동일하므로 강제 격상 사유 ↔ 큐 사유는
    `ReinspectionReason(forced_reason.value)` 로 그대로 변환된다.
    `SCORE_REJECT` 만 F-05 점수 기반(강제 격상 없음 + REJECT) 으로 추가된다.
    """

    SCORE_REJECT = "SCORE_REJECT"
    MATERIAL_UNREGISTERED = "MATERIAL_UNREGISTERED"
    MATERIAL_MISMATCH = "MATERIAL_MISMATCH"
    THICKNESS_RATIO_OVER = "THICKNESS_RATIO_OVER"
    ELECTRODE_SHAPE_MISMATCH = "ELECTRODE_SHAPE_MISMATCH"


class ReinspectionResult(BaseModel):
    """재검 결과 (큐에 임베드). F-08 학습 환류의 입력이 된다."""

    is_defect: bool = Field(
        ..., description="실제 불량 여부. True=불량 확정 / False=오탐(정상)."
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="검사 메모 (예: '가압력 부족 — 너깃 직경 3.8 mm').",
    )
    inspector_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="검사자 식별자 (예: 'WORKER-007').",
    )
    inspected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="검사 완료 시각 (UTC).",
    )


class ReinspectionQueue(Document):
    """재검 큐 도큐먼트 (`reinspection_queue` 컬렉션).

    `queue_id` 가 도메인 식별자(unique). `_id` 는 ObjectId 기본값.
    목록 조회는 `(status, created_at desc)` 인덱스로, 부품 필터는 `part_id`
    인덱스로 커버한다.
    """

    queue_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="큐 식별자 (예: 'rq_<hex>'). 서버 발급, unique.",
    )
    part_id: str = Field(
        ..., description="대상 부품 마스터 식별자."
    )
    event_ids: list[str] = Field(
        default_factory=list,
        description="이 큐에 묶인 트리거 이벤트들의 `WeldEvent.event_id`.",
    )
    status: ReinspectionStatus = Field(
        default=ReinspectionStatus.PENDING,
        description="큐 상태. 결과 등록 시 CLOSED 로 전이.",
    )
    reason: ReinspectionReason = Field(
        ...,
        description="큐를 처음 연 사유. 추가 트리거가 합쳐져도 갱신하지 않는다.",
    )
    result: ReinspectionResult | None = Field(
        default=None,
        description="재검 결과. CLOSED 상태일 때만 채워진다.",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="큐 생성 시각 (UTC).",
    )
    closed_at: datetime | None = Field(
        default=None,
        description="CLOSED 전이 시각 (UTC). 그 외 상태에서는 null.",
    )

    class Settings:
        name = "reinspection_queue"
        indexes = [
            IndexModel("queue_id", unique=True),
            IndexModel([("status", 1), ("created_at", -1)]),
            IndexModel("part_id"),
        ]
