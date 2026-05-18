"""F-07. 알림 이력 — Beanie Document.

웹소켓 푸시(`notifier.publish`) 가 휘발성이라 새로고침/재접속 시 과거 알림이
사라진다. 사이드바 unread 배지와 알림 패널 모달이 동작하려면 영구 저장이
필요해 별도 컬렉션으로 분리한다.

저장 조건: 판정 결과가 🟡 CAUTION 또는 🔴 REJECT 인 경우만. 🟢 NORMAL 은
이벤트는 많고 알릴 가치는 낮아 저장하지 않는다.
"""

from datetime import datetime, timezone
from enum import Enum

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.models.weld_event import ForcedReason, JudgementStatus


class NotificationSeverity(str, Enum):
    """알림 심각도. WeldEvent.judgement.status 와 매핑되지만 향후 시스템
    알림(예: PLC 연결 끊김) 도 같은 채널로 흘릴 수 있어 분리."""

    INFO = "INFO"        # 시스템 알림 (e.g., 학습 완료)
    WARNING = "WARNING"  # 🟡 CAUTION
    CRITICAL = "CRITICAL"  # 🔴 REJECT


class Notification(Document):
    """알림 이력 도큐먼트 (`notifications` 컬렉션).

    `read_at` 이 null 인 건수가 사이드바 unread 배지 카운트.
    """

    severity: NotificationSeverity = Field(
        ..., description="알림 심각도."
    )
    title: str = Field(
        ..., max_length=120, description="알림 제목 (예: '재검권장 발생')."
    )
    message: str = Field(
        ..., max_length=500, description="알림 본문 (한국어, 그대로 표시 가능)."
    )

    # 출처 추적용 — 클릭 시 상세 페이지로 라우팅하기 위한 식별자들.
    event_id: str | None = Field(
        default=None, description="연관 WeldEvent.event_id (있을 때만)."
    )
    queue_id: str | None = Field(
        default=None, description="연관 ReinspectionQueue.queue_id (있을 때만)."
    )
    line_id: str | None = Field(
        default=None, description="라인 식별자 (필터용)."
    )
    part_id: str | None = Field(
        default=None, description="부품 식별자 (필터용)."
    )
    status: JudgementStatus | None = Field(
        default=None, description="원본 판정 상태 (있을 때)."
    )
    forced_reason: ForcedReason | None = Field(
        default=None, description="강제 격상 사유 (있을 때)."
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    read_at: datetime | None = Field(
        default=None,
        description="읽음 표시 시각. null 이면 unread.",
    )

    class Settings:
        name = "notifications"
        indexes = [
            IndexModel([("created_at", -1)]),
            IndexModel([("read_at", 1), ("created_at", -1)]),
        ]
