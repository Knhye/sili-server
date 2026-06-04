"""Phase 3 (F-06/F-07/F-09) E2E 자동 검증 스크립트.

표준 라이브러리만 사용. 사용법:

    # 서버 띄운 상태에서
    python tests/manual/phase3/run_flow.py
    python tests/manual/phase3/run_flow.py --base-url http://localhost:8000

WebSocket 검증은 별도 — README 의 "WS 수동 검증" 절 참고.

스크립트는 멱등하게 설계 — 같은 part_id 가 이미 있으면 PATCH 로 갱신하고
계속 진행한다. 재검 결과 등록은 첫 번째 PENDING 큐 1건에만 수행한다.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures.json"

_ALLOWED_SCHEMES = {"http", "https"}


def _validate_base_url(base: str) -> str:
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        raise ValueError(f"유효하지 않은 base URL: {base!r} (http/https 만 허용)")
    return base.rstrip("/")


def _path(value: str) -> str:
    """URL 경로 세그먼트를 안전하게 인코딩."""
    return urllib.parse.quote(str(value), safe="")


# --------------------------------------------------------------------------- #
# HTTP 헬퍼
# --------------------------------------------------------------------------- #


def _request(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        raise ValueError(f"유효하지 않은 요청 URL: {url!r}")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {"raw": str(e)}
        return e.code, payload


def get(url: str) -> tuple[int, dict]:
    return _request("GET", url)


def post(url: str, body: dict) -> tuple[int, dict]:
    return _request("POST", url, body)


def patch(url: str, body: dict) -> tuple[int, dict]:
    return _request("PATCH", url, body)


def delete(url: str) -> tuple[int, dict]:
    return _request("DELETE", url)


# --------------------------------------------------------------------------- #
# 단계별 검증
# --------------------------------------------------------------------------- #


def assert_eq(label: str, actual, expected) -> bool:
    ok = actual == expected
    tag = "OK  " if ok else "FAIL"
    print(f"  {tag} | {label}: actual={actual!r} expected={expected!r}")
    return ok


def strip_underscore_keys(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def step_register_part(base: str, part: dict) -> bool:
    print("\n[STEP 1] 부품 마스터 등록")
    status, resp = post(f"{base}/api/v1/parts", strip_underscore_keys(part))
    if status == 409:
        print(f"  INFO | 이미 존재 — PATCH 로 갱신 (part_id={part['part_id']})")
        update = {
            k: v
            for k, v in part.items()
            if k not in ("_note", "part_id") and not k.startswith("_")
        }
        status, resp = patch(f"{base}/api/v1/parts/{_path(part['part_id'])}", update)
        return assert_eq("PATCH 응답 코드", status, 200)
    return assert_eq("POST 응답 코드", status, 201)


def step_ingest_events(base: str, events: list[dict]) -> list[dict]:
    """이벤트 6건 POST. 각 응답의 judgement 가 예상과 일치하는지 확인."""
    print("\n[STEP 2] 타점 이벤트 6건 송신 + 즉시 판정 검증")
    saved: list[dict] = []
    for i, ev in enumerate(events, 1):
        expected = ev["_expected"]
        payload = strip_underscore_keys(ev)
        status, resp = post(f"{base}/api/v1/weld-events", payload)
        if status != 201:
            print(f"  FAIL | event#{i}: HTTP {status} body={resp}")
            continue
        data = resp["data"]
        j = data.get("judgement") or {}
        ok_status = j.get("status") == expected["status"]
        ok_force = j.get("forced_reason") == expected.get("forced_reason")
        tag = "OK  " if (ok_status and ok_force) else "FAIL"
        print(
            f"  {tag} | event#{i} ({ev['point_id']}): "
            f"status={j.get('status')} forced={j.get('forced_reason')} "
            f"score={j.get('score')} (expected {expected['status']}/{expected.get('forced_reason')})"
        )
        saved.append({"event": data, "expected": expected})
    return saved


def step_check_latest(base: str) -> bool:
    print("\n[STEP 3] F-07 폴링: GET /events/latest")
    status, resp = get(f"{base}/api/v1/events/latest")
    ok1 = assert_eq("HTTP 200", status, 200)
    data = resp.get("data")
    ok2 = data is not None and data.get("point_id") == "P-006"
    print(f"  {'OK  ' if ok2 else 'FAIL'} | latest.point_id == P-006: actual={data and data.get('point_id')}")

    status, resp = get(f"{base}/api/v1/events/latest?status=NORMAL")
    data = resp.get("data")
    ok3 = data is not None and data.get("point_id") == "P-001"
    print(f"  {'OK  ' if ok3 else 'FAIL'} | latest?status=NORMAL == P-001: actual={data and data.get('point_id')}")
    return ok1 and ok2 and ok3


def step_check_queues(base: str) -> list[dict]:
    print("\n[STEP 4] F-06 재검 큐: GET /reinspection?status=PENDING")
    status, resp = get(f"{base}/api/v1/reinspection?status=PENDING&limit=200")
    if status != 200:
        print(f"  FAIL | HTTP {status}")
        return []
    queues = resp["data"]
    # TEST-PHASE3 큐만 필터
    queues = [q for q in queues if q["part_id"] == "TEST-PHASE3"]
    expected_reasons = {
        "THICKNESS_RATIO_OVER",
        "MATERIAL_MISMATCH",
        "ELECTRODE_SHAPE_MISMATCH",
        "SCORE_REJECT",
    }
    got_reasons = {q["reason"] for q in queues}
    ok_count = len(queues) == 4
    ok_set = got_reasons == expected_reasons
    print(f"  {'OK  ' if ok_count else 'FAIL'} | PENDING 큐 4건: actual={len(queues)}")
    print(f"  {'OK  ' if ok_set else 'FAIL'} | 사유 집합 일치: {sorted(got_reasons)}")
    return queues


def step_submit_result(base: str, queues: list[dict], result: dict) -> bool:
    print("\n[STEP 5] F-06 재검 결과 등록 → CLOSED 전이")
    if not queues:
        print("  SKIP | 큐 없음")
        return False
    target = queues[0]
    qid = target["queue_id"]
    status, resp = post(
        f"{base}/api/v1/reinspection/{_path(qid)}/result", strip_underscore_keys(result)
    )
    ok1 = assert_eq("HTTP 201", status, 201)
    ok2 = resp.get("data", {}).get("status") == "CLOSED"
    print(f"  {'OK  ' if ok2 else 'FAIL'} | status == CLOSED")

    status, resp = post(
        f"{base}/api/v1/reinspection/{_path(qid)}/result", strip_underscore_keys(result)
    )
    ok3 = assert_eq("재등록 시 409", status, 409)
    return ok1 and ok2 and ok3


def step_history_filters(base: str) -> bool:
    print("\n[STEP 6] F-09 이력 필터")
    status, resp = get(f"{base}/api/v1/weld-events?part_id=TEST-PHASE3&limit=200")
    docs = resp["data"]
    ok1 = len(docs) >= 6
    print(f"  {'OK  ' if ok1 else 'FAIL'} | part_id 필터: 6+ 건 (actual={len(docs)})")

    status, resp = get(
        f"{base}/api/v1/weld-events?part_id=TEST-PHASE3&status=REJECT"
    )
    docs = resp["data"]
    ok2 = len(docs) == 1 and docs[0]["point_id"] == "P-006"
    print(f"  {'OK  ' if ok2 else 'FAIL'} | status=REJECT 필터 → P-006 1건")

    status, resp = get(
        f"{base}/api/v1/weld-events?part_id=TEST-PHASE3&status=NORMAL"
    )
    docs = resp["data"]
    ok3 = len(docs) == 1 and docs[0]["point_id"] == "P-001"
    print(f"  {'OK  ' if ok3 else 'FAIL'} | status=NORMAL 필터 → P-001 1건")

    status, resp = get(
        f"{base}/api/v1/weld-events?part_id=TEST-PHASE3"
        "&from=2026-05-17T10:02:00Z&to=2026-05-17T10:04:00Z"
    )
    docs = resp["data"]
    points = sorted([d["point_id"] for d in docs])
    ok4 = points == ["P-003", "P-004", "P-005"]
    print(f"  {'OK  ' if ok4 else 'FAIL'} | 시간 범위(10:02~10:04) → P-003/004/005: {points}")

    status, resp = get(
        f"{base}/api/v1/weld-events?from=2026-05-17T10:10:00Z&to=2026-05-17T10:00:00Z"
    )
    ok5 = status == 400
    print(f"  {'OK  ' if ok5 else 'FAIL'} | from>to → 400: actual={status}")

    return all([ok1, ok2, ok3, ok4, ok5])


def step_judgement_detail(base: str) -> bool:
    print("\n[STEP 7] F-09 판정 상세")
    _, resp = get(f"{base}/api/v1/weld-events?part_id=TEST-PHASE3&status=REJECT")
    event_id = resp["data"][0]["event_id"]
    status, resp = get(f"{base}/api/v1/judgements/{_path(event_id)}")
    ok1 = assert_eq("HTTP 200", status, 200)
    j = resp["data"]
    ok2 = j["event_id"] == event_id and j["status"] == "REJECT"
    print(f"  {'OK  ' if ok2 else 'FAIL'} | event_id 일치 + status=REJECT")

    status, _ = get(f"{base}/api/v1/judgements/evt_nonexistent")
    ok3 = status == 404
    print(f"  {'OK  ' if ok3 else 'FAIL'} | 미존재 event_id → 404 (actual={status})")
    return ok1 and ok2 and ok3


def step_csv_export(base: str) -> bool:
    print("\n[STEP 8] F-09 CSV 내보내기")
    parsed = urllib.parse.urlparse(base)
    url = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        "/api/v1/exports/weld-events.csv",
        "",
        "part_id=TEST-PHASE3",
        "",
    ))
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as r:
        ctype = r.headers.get("Content-Type", "")
        disp = r.headers.get("Content-Disposition", "")
        body = r.read().decode("utf-8")
    ok1 = "text/csv" in ctype
    ok2 = "attachment" in disp and ".csv" in disp
    lines = [ln for ln in body.split("\n") if ln.strip()]
    ok3 = lines[0].startswith("event_id,timestamp,part_id")
    ok4 = len(lines) >= 7  # 헤더 + 6건
    print(f"  {'OK  ' if ok1 else 'FAIL'} | Content-Type text/csv: {ctype}")
    print(f"  {'OK  ' if ok2 else 'FAIL'} | Content-Disposition attachment: {disp}")
    print(f"  {'OK  ' if ok3 else 'FAIL'} | 헤더 라인 정상")
    print(f"  {'OK  ' if ok4 else 'FAIL'} | 데이터 라인 6+ (actual={len(lines)-1})")
    return all([ok1, ok2, ok3, ok4])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    args = ap.parse_args()

    base_url = _validate_base_url(args.base_url)
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))

    results: list[tuple[str, bool]] = []
    results.append(("part 등록", step_register_part(base_url, fixtures["part"])))
    saved = step_ingest_events(base_url, fixtures["events"])
    results.append(("이벤트 6건 ingest", len(saved) == 6))
    results.append(("F-07 latest", step_check_latest(base_url)))
    queues = step_check_queues(base_url)
    results.append(("F-06 큐 4건", len(queues) == 4))
    results.append((
        "F-06 결과 등록 + 중복 409",
        step_submit_result(
            base_url, queues, fixtures["reinspection_result_sample"]
        ),
    ))
    results.append(("F-09 이력 필터", step_history_filters(base_url)))
    results.append(("F-09 판정 상세", step_judgement_detail(base_url)))
    results.append(("F-09 CSV 내보내기", step_csv_export(base_url)))

    print("\n" + "=" * 60)
    print("결과 요약")
    print("=" * 60)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'} | {name}")
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n총 {len(results)}건 중 실패 {failed}건")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
