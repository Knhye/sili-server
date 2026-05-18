"""F-07. 현장 알림 — REST(폴링·이력) + WebSocket(실시간 푸시).

- GET  /api/v1/events/latest        : 최신 판정 결과 (폴링 폴백, status 필터)
- WS   /api/v1/ws/events            : 실시간 판정 푸시 스트림
- GET  /api/v1/notifications        : 알림 이력 (사이드바·알림 패널)
- GET  /api/v1/notifications/unread-count : unread 배지 카운트
- POST /api/v1/notifications/mark-read    : 읽음 처리 (선택/전체)

알림 규칙 (docs F-07)
  🟢 NORMAL : 화면 초록 (알림 저장 안 함)
  🟡 CAUTION: LED 황 + 화면 경고 → notifications WARNING
  🔴 REJECT : LED 적 + 부저 + 팝업 → notifications CRITICAL

WS 메시지 포맷
  {"type": "judgement", "data": <WeldEventRead>}
  - envelope 형식으로 향후 메시지 종류(예: 재검 큐 갱신) 추가에 대비.
  - 클라이언트 재연결 시 유실분은 `/events/latest` 폴링으로 복원.
"""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.response import ApiResponse, success_response
from app.models.notification import NotificationSeverity
from app.models.weld_event import JudgementStatus
from app.schemas.notification import (
    NotificationMarkReadRequest,
    NotificationRead,
)
from app.schemas.weld_event import WeldEventRead
from app.services.notification_service import (
    count_unread,
    list_notifications,
    mark_read,
)
from app.services.notifier import notifier
from app.services.weld_event_service import get_latest_weld_event

router = APIRouter(tags=["notifications"])


@router.get(
    "/events/latest",
    response_model=ApiResponse[WeldEventRead | None],
    summary="최신 판정 결과 조회 (폴링)",
)
async def get_latest_endpoint(
    status_: JudgementStatus | None = Query(
        default=None,
        alias="status",
        description="판정 상태 필터(NORMAL/CAUTION/REJECT).",
    ),
):
    event = await get_latest_weld_event(status=status_)
    data = (
        WeldEventRead.from_document(event).model_dump(mode="json")
        if event is not None
        else None
    )
    return success_response(data=data)


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket) -> None:
    """판정 결과 실시간 스트림. accept → subscribe → 큐 소비 루프.

    클라이언트 강제 종료 시 `WebSocketDisconnect` 로 빠져나가 큐를 정리.
    초기 상태(연결 직후의 최신값) 는 보내지 않는다 — 필요 시 클라이언트가
    `/events/latest` 를 호출.
    """
    await ws.accept()
    queue = await notifier.subscribe()
    try:
        while True:
            payload = await queue.get()
            await ws.send_json(payload)
    except WebSocketDisconnect:
        return
    finally:
        await notifier.unsubscribe(queue)


# --------------------------------------------------------------------------- #
# 알림 이력 (영구 저장)
# --------------------------------------------------------------------------- #


@router.get(
    "/notifications",
    response_model=ApiResponse[list[NotificationRead]],
    summary="알림 이력 조회 (필터·페이지네이션)",
)
async def list_notifications_endpoint(
    only_unread: bool = Query(
        default=False, description="True 시 unread 만 반환."
    ),
    severity: NotificationSeverity | None = Query(
        default=None, description="심각도 필터(INFO/WARNING/CRITICAL)."
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    docs = await list_notifications(
        only_unread=only_unread,
        severity=severity,
        skip=skip,
        limit=limit,
    )
    return success_response(
        data=[NotificationRead.from_document(d).model_dump(mode="json") for d in docs]
    )


@router.get(
    "/notifications/unread-count",
    response_model=ApiResponse[dict],
    summary="unread 알림 개수 (사이드바 배지)",
)
async def get_unread_count_endpoint():
    n = await count_unread()
    return success_response(data={"unread": n})


@router.post(
    "/notifications/mark-read",
    response_model=ApiResponse[dict],
    summary="알림 읽음 처리 (선택/전체)",
)
async def mark_read_endpoint(payload: NotificationMarkReadRequest):
    updated = await mark_read(payload.ids)
    return success_response(
        data={"updated": updated}, message="Marked as read"
    )
