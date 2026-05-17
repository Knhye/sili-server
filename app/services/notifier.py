"""F-07. 현장 알림 — 인-프로세스 WebSocket 브로드캐스터.

판정 결과(F-04/F-05) 가 ingest 흐름 끝에서 생성될 때마다 `publish()` 가
호출되어 모든 활성 구독자(WS 핸들러) 에게 비차단으로 푸시한다.

설계 가정 (v1 범위)
  - 단일 uvicorn 프로세스. 다중 워커 구성에서는 같은 워커의 구독자에게만
    전달됨 → 수평 확장 필요 시 Redis pub/sub 또는 Mongo change stream
    으로 교체.
  - 느린 클라이언트는 큐 오버플로우(`maxsize=100`) 시점에 자동 제거되어
    publisher 가 영원히 막히지 않도록 한다.
  - asyncio 단일 스레드 모델이라 `put_nowait` 와 set 변경 사이에 await
    경계가 없으면 별도 락 없이 안전하다.
"""

import asyncio
from typing import Any


class JudgementNotifier:
    """판정 결과 실시간 브로드캐스터.

    `subscribe()` 가 반환하는 큐를 클라이언트(웹소켓 핸들러) 가 `await get()`
    으로 소비한다. 각 큐는 독립적이므로 한 클라이언트의 정체가 다른 클라
    이언트에 영향을 주지 않는다 (대신 정체된 큐는 결국 가득 차서 자기만
    제거됨).
    """

    def __init__(self, queue_size: int = 100) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._queue_size = queue_size

    async def publish(self, payload: dict[str, Any]) -> None:
        """모든 구독자에게 비차단 적재. 큐가 가득 찬 구독자는 즉시 제거."""
        dead: list[asyncio.Queue[dict[str, Any]]] = []
        # 이터레이션 중 set 변경을 막기 위해 snapshot.
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


notifier = JudgementNotifier()
