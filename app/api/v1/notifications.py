"""F-07. 현장 알림 — REST(폴링) + WebSocket(실시간 푸시).

- GET /api/v1/events/latest : 최신 판정 결과 (폴링 폴백, status 필터)
- WS  /api/v1/ws/events     : 실시간 판정 푸시 스트림

알림 규칙 (docs F-07)
  🟢 NORMAL : 화면 초록
  🟡 CAUTION: LED 황 + 화면 경고
  🔴 REJECT : LED 적 + 부저 + 팝업

WS 메시지 포맷
  {"type": "judgement", "data": <WeldEventRead>}
  - envelope 형식으로 향후 메시지 종류(예: 재검 큐 갱신) 추가에 대비.
  - 클라이언트 재연결 시 유실분은 `/events/latest` 폴링으로 복원.
"""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.response import ApiResponse, success_response
from app.models.weld_event import JudgementStatus
from app.schemas.weld_event import WeldEventRead
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
