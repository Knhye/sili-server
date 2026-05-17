# Phase 3 수동 테스트 — F-06 / F-07 / F-09

Phase 3 의 3가지 기능을 한 시나리오로 묶어서 종단(end-to-end) 검증한다.

| 기능 | 검증 포인트 |
| --- | --- |
| F-06 재검 큐 관리 | 🔴/강제 격상 판정 시 자동 enqueue, PENDING 목록, 결과 등록 → CLOSED 전이, 중복 등록 409 |
| F-07 현장 알림 | `GET /events/latest` 폴링, `WS /ws/events` 실시간 푸시 |
| F-09 이력·추적성 | `GET /weld-events` 필터(part/status/from/to), `GET /judgements/{event_id}`, CSV 내보내기 |

## 사전 준비

1. MongoDB 연결 가능 (앱이 부팅하면서 `config` 컬렉션을 자동 시드함).
2. 앱 실행:
   ```powershell
   uvicorn app.main:app --reload
   ```
3. 헬스 체크:
   ```powershell
   Invoke-RestMethod http://localhost:8000/
   ```

## 시나리오 개요 (이벤트 6건, 큐 4건)

`TEST-PHASE3` 부품 1대에 6개 타점(P-001~P-006)을 송신한다. 각 타점은
설계상 다음 결과를 만든다.

| # | point | 변형 | 기대 status | forced_reason | 큐 생성 |
| --- | --- | --- | --- | --- | --- |
| 1 | P-001 | 중앙값 정상 | 🟢 NORMAL | — | ❌ |
| 2 | P-002 | 가압력 –35% (1.7 kN) | 🟡 CAUTION (score≈41) | — | ❌ |
| 3 | P-003 | 두께 비 4.0 (0.5/2.0) | 🟡 CAUTION (강제) | THICKNESS_RATIO_OVER | ✅ |
| 4 | P-004 | 재질 HSLA (마스터 MILD) | 🟡 CAUTION (강제) | MATERIAL_MISMATCH | ✅ |
| 5 | P-005 | R-TYPE (권장 C-TYPE) | 🟡 CAUTION (강제) | ELECTRODE_SHAPE_MISMATCH | ✅ |
| 6 | P-006 | 복합 이상 (전류/시간/가압력 동시 이탈) | 🔴 REJECT (score=100) | — | ✅ (SCORE_REJECT) |

→ PENDING 큐 4건 (P-003/004/005/006).
→ 점수 기반 CAUTION(이벤트 #2) 은 docs F-05 "주의는 큐 등록 X" 규칙대로 큐 생성 안 됨.

## 자동 실행 (권장)

```powershell
python tests/manual/phase3/run_flow.py
# 다른 호스트:
python tests/manual/phase3/run_flow.py --base-url http://localhost:8000
```

스크립트가 단계별로 `OK / FAIL` 을 출력하고 마지막에 요약을 찍는다. 모든
단계가 PASS 면 Phase 3 가 docs 명세대로 동작한다는 의미.

## 수동 실행 (단계별)

PowerShell 기준. 각 단계의 기대 응답을 같이 적었다. WS 단계는 별도 도구 필요.

### Step 1 — 부품 마스터 등록

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/parts `
  -ContentType 'application/json' `
  -Body (Get-Content tests/manual/phase3/fixtures.json | ConvertFrom-Json).part `
        .'@{}'  # 또는 fixtures.json 의 part 객체를 그대로 PUT
```

간단히:
```powershell
$part = (Get-Content tests/manual/phase3/fixtures.json -Raw | ConvertFrom-Json).part
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/parts -ContentType 'application/json' -Body ($part | ConvertTo-Json -Depth 5)
```

기대: `success: true, code: 201`. 이미 있으면 409 → PATCH 로 갱신.

### Step 2 — WS 구독 시작 (선택)

별도 터미널에서:

**브라우저 콘솔**
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/events');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

**wscat (npm install -g wscat)**
```bash
wscat -c ws://localhost:8000/api/v1/ws/events
```

Step 3 에서 6건 POST 할 때마다 envelope 메시지가 푸시됨:
```json
{"type": "judgement", "data": { "event_id": "evt_...", "judgement": {"status": "...", ... } }}
```

### Step 3 — 이벤트 6건 송신

`fixtures.json` 의 `events` 배열 6건을 순서대로 POST.

```powershell
$events = (Get-Content tests/manual/phase3/fixtures.json -Raw | ConvertFrom-Json).events
foreach ($e in $events) {
  $payload = $e.PSObject.Properties | Where-Object Name -notlike '_*' |
             ForEach-Object -Begin {$h=@{}} -Process {$h[$_.Name]=$_.Value} -End {$h}
  $resp = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/weld-events `
            -ContentType 'application/json' -Body ($payload | ConvertTo-Json -Depth 5)
  Write-Host ("{0} → {1} / forced={2} / score={3}" -f
    $e.point_id, $resp.data.judgement.status, $resp.data.judgement.forced_reason, $resp.data.judgement.score)
}
```

기대 출력 (대략):
```
P-001 → NORMAL  / forced=        / score=0
P-002 → CAUTION / forced=        / score=40.7
P-003 → CAUTION / forced=THICKNESS_RATIO_OVER  / score=31
P-004 → CAUTION / forced=MATERIAL_MISMATCH     / score=31
P-005 → CAUTION / forced=ELECTRODE_SHAPE_MISMATCH / score=31
P-006 → REJECT  / forced=        / score=100
```

WS를 열어뒀다면 동시에 6건 envelope 가 푸시된다.

### Step 4 — F-07 폴링 검증

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/events/latest
# data.point_id == P-006 (가장 최근 timestamp)

Invoke-RestMethod 'http://localhost:8000/api/v1/events/latest?status=NORMAL'
# data.point_id == P-001
```

### Step 5 — F-06 재검 큐 목록

```powershell
Invoke-RestMethod 'http://localhost:8000/api/v1/reinspection?status=PENDING&limit=200' |
  Select-Object -ExpandProperty data |
  Where-Object part_id -eq 'TEST-PHASE3' |
  Select-Object queue_id, reason, event_ids, status
```

기대: 4행. `reason` 4종 (`THICKNESS_RATIO_OVER`, `MATERIAL_MISMATCH`,
`ELECTRODE_SHAPE_MISMATCH`, `SCORE_REJECT`), 각 `event_ids` 는 길이 1.

### Step 6 — 재검 결과 등록 (CLOSED 전이)

목록에서 `queue_id` 하나를 골라 결과 등록.

```powershell
$qid = 'rq_여기에_복사'
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/reinspection/$qid/result" `
  -ContentType 'application/json' `
  -Body '{"is_defect": true, "inspector_id": "WORKER-007", "notes": "가압력 부족"}'
```

기대: `status == CLOSED`, `closed_at` 채워짐.

같은 큐에 재등록 시 409 확인:
```powershell
# 같은 명령 한 번 더 → 409 "이미 종료된 재검 큐입니다"
```

### Step 7 — F-09 필터

```powershell
# part 전체
Invoke-RestMethod 'http://localhost:8000/api/v1/weld-events?part_id=TEST-PHASE3&limit=200' |
  Select-Object -ExpandProperty data | Measure-Object   # Count == 6

# REJECT만
Invoke-RestMethod 'http://localhost:8000/api/v1/weld-events?part_id=TEST-PHASE3&status=REJECT' |
  Select-Object -ExpandProperty data   # P-006 1건

# 시간 범위
Invoke-RestMethod 'http://localhost:8000/api/v1/weld-events?part_id=TEST-PHASE3&from=2026-05-17T10:02:00Z&to=2026-05-17T10:04:00Z' |
  Select-Object -ExpandProperty data   # P-003/004/005

# from > to → 400
try {
  Invoke-RestMethod 'http://localhost:8000/api/v1/weld-events?from=2026-05-17T10:10:00Z&to=2026-05-17T10:00:00Z'
} catch { $_.Exception.Response.StatusCode }   # BadRequest
```

### Step 8 — F-09 판정 상세

```powershell
$rejectEvent = (Invoke-RestMethod 'http://localhost:8000/api/v1/weld-events?part_id=TEST-PHASE3&status=REJECT').data[0]
Invoke-RestMethod "http://localhost:8000/api/v1/judgements/$($rejectEvent.event_id)"
# event_id 일치, status: REJECT, deviations 채워짐
```

### Step 9 — F-09 CSV 내보내기

```powershell
Invoke-WebRequest 'http://localhost:8000/api/v1/exports/weld-events.csv?part_id=TEST-PHASE3' `
  -OutFile phase3.csv
Get-Content phase3.csv | Select-Object -First 3
```

기대: 첫 줄이 `event_id,timestamp,part_id,...` 헤더, 이후 6행 데이터.
`judgement_*` 컬럼이 NORMAL/CAUTION/REJECT 로 채워져 있다.

## 정리 (선택)

테스트 데이터를 깔끔히 지우려면:

```powershell
# 부품 + 관련 이벤트/큐는 자동 cascade 가 없으므로 컬렉션 직접 정리
# 또는 Mongo 셸:
#   db.weld_events.deleteMany({part_id: "TEST-PHASE3"})
#   db.reinspection_queue.deleteMany({part_id: "TEST-PHASE3"})
#   db.parts.deleteOne({part_id: "TEST-PHASE3"})

Invoke-RestMethod -Method Delete http://localhost:8000/api/v1/parts/TEST-PHASE3
```

## 주의 사항

- `run_flow.py` 는 멱등하지만 **누적**된다. 반복 실행하면 weld_events 가
  같은 timestamp 로 계속 쌓인다. 깨끗한 검증 원하면 사이마다 collection
  정리.
- WS 자동 검증은 스크립트에 포함되지 않음 — Step 2 참고하여 별도 클라이
  언트로 확인.
- 시드 config 값(`thickness_limits["0.8+1.2"]` 등)이 바뀌면 P-002/P-006
  의 예상 점수가 어긋날 수 있다.
