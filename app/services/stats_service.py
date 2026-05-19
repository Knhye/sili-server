"""대시보드 KPI 집계 — 교대(shift) 합격률 + 시간당 생산.

교대(shift) 정의는 docs 에 명시되지 않아 단순 규칙으로 산정한다:
  - 클라이언트가 `hours` 윈도우(기본 8h) 를 지정.
  - 라인 필터(`line_id`) 옵션.
  - 합격률 = NORMAL / 판정 완료 건수 (판정 없는 이벤트는 분모에서 제외).
  - 시간당 생산 = 윈도우 내 총 이벤트 수 / 시간수.

이 모듈은 read-only. WeldEvent 컬렉션을 직접 aggregate 한다.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.weld_event import JudgementStatus, WeldEvent


_DEFAULT_HOURS = 8


async def get_shift_stats(
    *,
    hours: int = _DEFAULT_HOURS,
    line_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """교대 윈도우 합격률 + 시간당 생산.

    Args:
        hours: 윈도우 시간 길이. 기본 8h.
        line_id: 필터. None 이면 전체 라인 합산.
        now: 종료 시각(테스트용). None 이면 현재 UTC.

    Returns:
        - window_start, window_end (ISO 8601 UTC)
        - hours: 윈도우 길이
        - total: 윈도우 내 이벤트 수
        - judged: 판정 완료 이벤트 수
        - normal/caution/reject: 상태별 건수
        - pass_rate: 합격률 (0~1, 판정 완료 기준). judged==0 이면 None.
        - hourly_rate: 시간당 생산 (total/hours, 소수점 1자리).
    """
    if now is not None:
        end = now
    else:
        real_now = datetime.now(timezone.utc)
        anchor_filter: dict[str, Any] = {} if line_id is None else {"line_id": line_id}
        latest = await WeldEvent.find(anchor_filter).sort("-timestamp").first_or_none()
        if latest is not None:
            latest_ts = latest.timestamp
            if latest_ts.tzinfo is None:
                latest_ts = latest_ts.replace(tzinfo=timezone.utc)
            end = latest_ts if latest_ts < real_now else real_now
        else:
            end = real_now

    start = end - timedelta(hours=hours)

    base: dict[str, Any] = {"timestamp": {"$gte": start, "$lte": end}}
    if line_id is not None:
        base["line_id"] = line_id

    total = await WeldEvent.find(base).count()
    judged_query = {**base, "judgement": {"$ne": None}}
    judged = await WeldEvent.find(judged_query).count()

    counts: dict[str, int] = {}
    for status in JudgementStatus:
        q = {**base, "judgement.status": status.value}
        counts[status.value.lower()] = await WeldEvent.find(q).count()

    pass_rate: float | None
    if judged == 0:
        pass_rate = None
    else:
        pass_rate = round(counts["normal"] / judged, 4)

    hourly_rate = round(total / hours, 1) if hours > 0 else 0.0

    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "hours": hours,
        "line_id": line_id,
        "total": total,
        "judged": judged,
        "normal": counts["normal"],
        "caution": counts["caution"],
        "reject": counts["reject"],
        "pass_rate": pass_rate,
        "hourly_rate": hourly_rate,
    }
