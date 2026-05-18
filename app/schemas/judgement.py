"""F-09. 이력·추적성 — 판정 결과 상세 DTO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.weld_event import (
    ForcedReason,
    JudgementDeviation,
    JudgementStatus,
    WeldEvent,
)


class JudgementDetailRead(BaseModel):
    """`GET /api/v1/judgements/{event_id}` 응답 본문.

    `WeldEvent.judgement` 임베드 모델 + 식별자(`event_id`). 판정이 없는
    이벤트는 서비스 레이어에서 404 로 분기되므로 여기 도달하지 않는다.
    """

    model_config = ConfigDict(from_attributes=True)

    event_id: str = Field(..., description="대상 WeldEvent 식별자.")
    score: float = Field(..., ge=0, le=100, description="이상 점수 (0~100).")
    status: JudgementStatus
    forced_reason: ForcedReason | None
    message: str = Field(
        default="", description="상태 배너용 한국어 메시지."
    )
    deviations: JudgementDeviation
    created_at: datetime

    @classmethod
    def from_event(cls, event: WeldEvent) -> "JudgementDetailRead":
        # 호출자(라우터)가 `event.judgement is not None` 을 보장.
        j = event.judgement
        assert j is not None
        return cls(
            event_id=event.event_id,
            score=j.score,
            status=j.status,
            forced_reason=j.forced_reason,
            message=j.message,
            deviations=j.deviations,
            created_at=j.created_at,
        )
