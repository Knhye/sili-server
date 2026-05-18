"""F-07. 알림 이력 — 서비스 레이어.

`record_judgement_notification()` 은 ingest 흐름 끝에서 호출되어 🟡/🔴
판정에 대한 알림 레코드를 1건 INSERT 한다. 실시간 WS 푸시(`notifier`)는
이 모듈과 독립적으로 동작 — 둘 다 같은 판정 결과를 입력으로 받지만 한쪽이
실패해도 다른 쪽은 영향을 받지 않는다 (best-effort).
"""

from datetime import datetime, timezone
from typing import Any

from beanie import PydanticObjectId
from bson.errors import InvalidId

from app.models.notification import Notification, NotificationSeverity
from app.models.weld_event import (
    ForcedReason,
    Judgement,
    JudgementStatus,
    WeldEvent,
)


_STATUS_TO_SEVERITY: dict[JudgementStatus, NotificationSeverity] = {
    JudgementStatus.CAUTION: NotificationSeverity.WARNING,
    JudgementStatus.REJECT: NotificationSeverity.CRITICAL,
}

_TITLES: dict[JudgementStatus, str] = {
    JudgementStatus.CAUTION: "주의 — 정상 범위 이탈",
    JudgementStatus.REJECT: "재검권장 — 즉시 확인",
}


async def record_judgement_notification(
    event: WeldEvent,
    judgement: Judgement,
    queue_id: str | None = None,
) -> Notification | None:
    """🟡 CAUTION / 🔴 REJECT 만 기록. 🟢 NORMAL 은 None 반환 + no-op."""
    severity = _STATUS_TO_SEVERITY.get(judgement.status)
    if severity is None:
        return None

    title = _TITLES.get(judgement.status, "판정 알림")
    # message 는 판정 엔진이 채운 한국어 문구를 그대로 사용 — 단일 출처.
    body = judgement.message or "판정 결과를 확인하세요."
    # part_id/타점 정보를 본문에 덧붙여 알림 패널에서 즉시 식별 가능하게.
    body = f"[{event.part_id}/{event.point_id}] {body}"

    notif = Notification(
        severity=severity,
        title=title,
        message=body,
        event_id=event.event_id,
        queue_id=queue_id,
        line_id=event.line_id,
        part_id=event.part_id,
        status=judgement.status,
        forced_reason=judgement.forced_reason,
    )
    await notif.insert()
    return notif


async def list_notifications(
    *,
    only_unread: bool = False,
    severity: NotificationSeverity | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Notification]:
    """최신순. 필터 적용 후 페이지네이션."""
    query: dict[str, Any] = {}
    if only_unread:
        query["read_at"] = None
    if severity is not None:
        query["severity"] = severity.value
    return (
        await Notification.find(query)
        .sort(-Notification.created_at)
        .skip(skip)
        .limit(limit)
        .to_list()
    )


async def count_unread() -> int:
    return await Notification.find({"read_at": None}).count()


async def mark_read(ids: list[str] | None) -> int:
    """ids=None 이면 전체 unread 를 읽음. 처리된 건수 반환."""
    now = datetime.now(timezone.utc)
    if ids is None:
        result = await Notification.get_motor_collection().update_many(
            {"read_at": None}, {"$set": {"read_at": now}}
        )
        return result.modified_count

    object_ids: list[PydanticObjectId] = []
    for s in ids:
        try:
            object_ids.append(PydanticObjectId(s))
        except (InvalidId, ValueError):
            # 잘못된 ID 는 조용히 무시 — 부분 성공 OK.
            continue
    if not object_ids:
        return 0
    result = await Notification.get_motor_collection().update_many(
        {"_id": {"$in": object_ids}, "read_at": None},
        {"$set": {"read_at": now}},
    )
    return result.modified_count
