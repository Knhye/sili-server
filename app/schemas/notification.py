"""F-07. 알림 이력 — Pydantic DTO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import Notification, NotificationSeverity
from app.models.weld_event import ForcedReason, JudgementStatus


class NotificationRead(BaseModel):
    """`GET /api/v1/notifications` 응답 항목."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    severity: NotificationSeverity
    title: str
    message: str
    event_id: str | None
    queue_id: str | None
    line_id: str | None
    part_id: str | None
    status: JudgementStatus | None
    forced_reason: ForcedReason | None
    created_at: datetime
    read_at: datetime | None

    @classmethod
    def from_document(cls, doc: Notification) -> "NotificationRead":
        return cls(
            id=str(doc.id),
            severity=doc.severity,
            title=doc.title,
            message=doc.message,
            event_id=doc.event_id,
            queue_id=doc.queue_id,
            line_id=doc.line_id,
            part_id=doc.part_id,
            status=doc.status,
            forced_reason=doc.forced_reason,
            created_at=doc.created_at,
            read_at=doc.read_at,
        )


class NotificationMarkReadRequest(BaseModel):
    """`POST /api/v1/notifications/mark-read` 요청 본문."""

    ids: list[str] | None = Field(
        default=None,
        description="읽음 처리할 ID 목록. 생략 시 unread 전체를 읽음 처리.",
    )
