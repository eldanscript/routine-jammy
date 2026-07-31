# Supabase 저장소 교체 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 저장소 계층을 Google Sheets/Apps Script에서 Supabase로 교체한다. 나머지 파이프라인은 건드리지 않는다.

**Architecture:** `sheet_client.py`를 같은 반환 계약을 지키는 `supabase_client.py`로 갈아끼운다. PostgREST를 secret 키로 조회하고, `(day, item)`별 최신 행만 남기고, `payload` JSONB를 최상위로 펼쳐 기존 파이프라인이 쓰던 모양 그대로 돌려준다. 프론트는 Apps Script 대신 PostgREST로 POST하며 사람별 쓰기 토큰을 헤더에 실어 보낸다.

**Tech Stack:** Python 3.12 + `requests`(기존), 순수 `fetch`(프론트, 빌드 도구 없음), Supabase(PostgREST + RLS).

## Global Constraints

- 테스트: 저장소 루트에서 `python3 -m pytest tests/ -q`. **현재 112개 통과.** 실패는 항상 0이어야 한다.
  개수는 Task 1~4·6에서 줄면 안 되고, **Task 5에서만 줄어도 된다** — 그 작업이 `test_sheet_client.py`를
  삭제하기 때문이다. Task 5에서 줄어드는 폭은 삭제한 파일의 테스트 수와 정확히 같아야 하며,
  그보다 더 줄었다면 다른 것을 망가뜨린 것이다.
- JS 테스트: `node --test tests/js/`
- `tests/conftest.py`가 `src/routine-jammy`를 `sys.path`에 넣는다 → `from supabase_client import ...`
- **C-1**: 아래 8개 모듈과 `tests/test_characterization.py`의 기대값은 **변경 금지**:
  `catalog.py`, `person.py`, `routine_rules.py`, `exercise_stats.py`, `history_store.py`, `nutrition_lookup.py`, `telegram_notifier.py`, `next_week_builder.py`
- **반환 계약**: `fetch_week(week_id, person)` → `{"responses": [...], "reflection": {...}}`. 각 response는 최소한 `day`, `item`, `checked`를 갖고, 식단 행은 `note`를 갖는다.
- **`Prefer: return=minimal`**: `anon`에 SELECT 권한이 없으므로 삽입 결과를 돌려받으려 하면 INSERT 전체가 실패한다. 프론트는 반드시 이 헤더를 보낸다.
- 새 의존성 추가 금지 (`supabase-py`, `supabase-js` 모두 안 쓴다).
- secret 키·쓰기 토큰은 `.env`에만. **커밋 금지.** publishable 키는 커밋해도 된다(공개 전제 키).

## 이미 완료된 것 (구현 불필요)

- Supabase 프로젝트 생성, `supabase/schema.sql` 적용 완료
- RLS 검증 11가지 수동 통과 (SELECT/UPDATE/DELETE 차단, 토큰 없는·틀린·타인 사칭 INSERT 차단, `created_at` 위조 차단, payload 4KB 초과 차단, secret 키 읽기 성공)
- `.env`에 `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `ROUTINE_JAMMY_TOKEN` 설정됨
- publishable 키: `sb_publishable_sCgRLsZ5rhY32D8dJj3PKw_GPG7gyfO`

## 환경 사실

- `checkins` 테이블은 **비어 있다**(검증 데이터 정리 완료). 마이그레이션할 기존 데이터 없음.
- 앱은 라이브: https://eldanscript.github.io/routine-jammy/ — 단 `config.js`가 비어 있어 현재 localStorage 전용으로 동작 중.
- 주간 크론이 일요일 18:00 KST에 이 작업 트리에서 돈다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `src/routine-jammy/supabase_client.py` (신규) | PostgREST 조회 + 최신행 선별 + payload 펼치기. 기존 `fetch_week` 계약 유지 |
| `src/routine-jammy/health_check.py` (신규) | 무료 티어 일시정지 방지용 일일 keepalive |
| `src/routine-jammy/weekly_refresh.py` (수정) | import 교체 |
| `docs/app.js` (수정) | POST 대상·형식 교체, 토큰 헤더 |
| `docs/config.js` (수정) | Supabase URL + publishable 키 |
| `tests/test_supabase_client.py` (신규) | 선별·펼치기 단위 테스트 (네트워크 없음) |
| `tests/test_rls_live.py` (신규) | RLS 검증 정식화 (네트워크 필요, 기본 스위트에서 제외) |
| `src/routine-jammy/sheet_client.py` | **삭제** |
| `tests/test_sheet_client.py` | **삭제** |
| `apps-script/` 전체 | **삭제** |
| `specs/plans/2026-07-31-sheet-migration-runbook.md` | **삭제** |

---

### Task 1: `supabase_client.py` — 조회·선별·펼치기

**Files:**
- Create: `src/routine-jammy/supabase_client.py`
- Create: `tests/test_supabase_client.py`

**Interfaces:**
- Produces:
  - `supabase_client.fetch_week(week_id: str, person: str | None = None) -> dict`
  - `supabase_client.SupabaseClientError`
  - `supabase_client.REFLECTION_ITEM = "회고"`
  - 내부 순수 함수 `_shape_week(rows: list[dict]) -> dict` — 테스트가 직접 호출한다

- [ ] **Step 1: 실패하는 테스트 작성**

```python
import pytest
from supabase_client import REFLECTION_ITEM, SupabaseClientError, _shape_week


def row(day, item, checked=True, payload=None, rid=1):
    return {
        "id": rid, "person_id": "jammy", "week_id": "2026-W31",
        "day": day, "item": item, "checked": checked,
        "payload": payload or {}, "created_at": "2026-08-01T00:00:00+00:00",
    }


def test_payload_is_flattened_to_top_level():
    rows = [row("월", "아점", payload={"note": "달걀 2"})]
    out = _shape_week(rows)
    assert out["responses"][0]["note"] == "달걀 2"
    assert out["responses"][0]["item"] == "아점"


def test_core_fields_win_over_payload():
    """조작된 payload가 checked 같은 코어 값을 덮어쓰면 안 된다."""
    rows = [row("월", "스쿼트", checked=True, payload={"checked": False, "item": "위조"})]
    out = _shape_week(rows)
    assert out["responses"][0]["checked"] is True
    assert out["responses"][0]["item"] == "스쿼트"


def test_later_row_wins_for_same_day_and_item():
    """행은 created_at 오름차순으로 들어온다고 가정한다 — 뒤에 온 것이 최신이다."""
    rows = [
        row("월", "스쿼트", checked=True, rid=1),
        row("월", "스쿼트", checked=False, rid=2),
    ]
    out = _shape_week(rows)
    assert len(out["responses"]) == 1
    assert out["responses"][0]["checked"] is False


def test_different_days_are_kept_separately():
    rows = [row("월", "스쿼트", rid=1), row("화", "스쿼트", rid=2)]
    out = _shape_week(rows)
    assert len(out["responses"]) == 2


def test_reflection_is_extracted_not_in_responses():
    rows = [
        row("월", "스쿼트"),
        row("일", REFLECTION_ITEM, payload={"good": "잘함", "blocker": "피곤", "change": "일찍자기"}),
    ]
    out = _shape_week(rows)
    assert [r["item"] for r in out["responses"]] == ["스쿼트"]
    assert out["reflection"] == {"good": "잘함", "blocker": "피곤", "change": "일찍자기"}


def test_reflection_dedupes_across_days_not_per_day():
    """회고는 주당 하나다. 다른 요일에 다시 써도 마지막 것만 남는다."""
    rows = [
        row("월", REFLECTION_ITEM, payload={"good": "첫번째", "blocker": "", "change": ""}, rid=1),
        row("수", REFLECTION_ITEM, payload={"good": "두번째", "blocker": "", "change": ""}, rid=2),
    ]
    out = _shape_week(rows)
    assert out["reflection"]["good"] == "두번째"
    assert out["responses"] == []


def test_missing_reflection_is_empty_dict():
    out = _shape_week([row("월", "스쿼트")])
    assert out["reflection"] == {}


def test_reflection_fills_missing_keys_with_empty_string():
    rows = [row("일", REFLECTION_ITEM, payload={"good": "있음"})]
    out = _shape_week(rows)
    assert out["reflection"] == {"good": "있음", "blocker": "", "change": ""}


def test_empty_rows_gives_empty_shape():
    assert _shape_week([]) == {"responses": [], "reflection": {}}


def test_null_payload_is_treated_as_empty():
    rows = [{**row("월", "스쿼트"), "payload": None}]
    out = _shape_week(rows)
    assert out["responses"][0]["checked"] is True


def test_fetch_week_requires_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    from supabase_client import fetch_week
    with pytest.raises(KeyError):
        fetch_week("2026-W31", person="jammy")


def test_fetch_week_sends_expected_query(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        def json(self):
            return []

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setattr("supabase_client.requests.get", fake_get)

    from supabase_client import fetch_week
    fetch_week("2026-W31", person="jammy")

    assert captured["url"] == "https://example.test/rest/v1/checkins"
    assert captured["params"]["person_id"] == "eq.jammy"
    assert captured["params"]["week_id"] == "eq.2026-W31"
    # 정렬은 Postgres에 맡긴다 — 클라이언트가 타임스탬프를 파싱하지 않는다
    assert captured["params"]["order"] == "created_at.asc,id.asc"
    assert captured["headers"]["apikey"] == "sb_secret_x"


def test_fetch_week_raises_on_non_200(monkeypatch):
    class FakeResponse:
        status_code = 500
        text = "boom"
        def json(self):
            return {}

    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setattr("supabase_client.requests.get",
                        lambda *a, **k: FakeResponse())

    from supabase_client import fetch_week
    with pytest.raises(SupabaseClientError, match="500"):
        fetch_week("2026-W31", person="jammy")
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_supabase_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'supabase_client'`

- [ ] **Step 3: 구현**

```python
"""Supabase(PostgREST) 저장소 클라이언트.

기존 sheet_client.fetch_week와 동일한 모양을 반환한다 — 그래야 파이프라인의 나머지
모듈(routine_rules, history_store, exercise_stats 등)을 건드리지 않는다.

읽기는 secret 키로 한다(RLS 우회). 이 모듈은 서버에서만 쓰이며 브라우저와 무관하다.
"""

import os

import requests

REFLECTION_ITEM = "회고"
_REFLECTION_KEYS = ("good", "blocker", "change")
_TIMEOUT = 15


class SupabaseClientError(RuntimeError):
    pass


def _shape_week(rows) -> dict:
    """PostgREST 행 목록을 파이프라인이 쓰는 모양으로 바꾼다.

    rows는 created_at 오름차순으로 들어온다고 가정한다(정렬은 Postgres가 한다).
    같은 (day, item)이 여러 번 나오면 뒤에 온 것이 최신이므로 덮어쓴다.
    회고는 주당 하나이므로 요일과 무관하게 마지막 것만 남긴다.
    """
    latest = {}
    reflection_row = None

    for row in rows:
        if row["item"] == REFLECTION_ITEM:
            reflection_row = row          # 오름차순이므로 마지막이 최신
            continue
        latest[(row["day"], row["item"])] = row

    responses = []
    for row in latest.values():
        payload = row.get("payload") or {}
        # payload를 먼저 펼치고 코어 필드를 나중에 씌운다 —
        # 조작된 payload가 checked/item/day를 덮어쓸 수 없게 하는 순서다.
        responses.append({
            **payload,
            "day": row["day"],
            "item": row["item"],
            "checked": row["checked"],
        })

    reflection = {}
    if reflection_row is not None:
        payload = reflection_row.get("payload") or {}
        reflection = {key: payload.get(key, "") for key in _REFLECTION_KEYS}

    return {"responses": responses, "reflection": reflection}


def fetch_week(week_id: str, person: str | None = None) -> dict:
    """해당 주차의 체크인을 가져와 파이프라인 모양으로 돌려준다.

    SUPABASE_URL, SUPABASE_SECRET_KEY 환경변수가 필요하다.
    """
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SECRET_KEY"]

    params = {
        "select": "*",
        "week_id": f"eq.{week_id}",
        # created_at 동률일 때를 위해 id를 2차 정렬키로 둔다.
        # 정렬을 Postgres에 맡기면 클라이언트가 타임스탬프를 파싱할 필요가 없다.
        "order": "created_at.asc,id.asc",
    }
    if person:
        params["person_id"] = f"eq.{person}"

    headers = {"apikey": secret, "Authorization": f"Bearer {secret}"}

    response = requests.get(
        f"{base_url}/rest/v1/checkins", params=params, headers=headers, timeout=_TIMEOUT
    )
    if response.status_code != 200:
        raise SupabaseClientError(
            f"Supabase GET failed with status {response.status_code}: {response.text}"
        )
    return _shape_week(response.json())
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_supabase_client.py -q`
Expected: 13 passed

- [ ] **Step 5: 전체 스위트**

Run: `python3 -m pytest tests/ -q`
Expected: 실패 0, 개수가 112보다 늘어난다

- [ ] **Step 6: 커밋**

```bash
git add src/routine-jammy/supabase_client.py tests/test_supabase_client.py
git commit -m "feat: add Supabase storage client

Returns the same shape sheet_client did, so the rest of the pipeline needs
no changes. Ordering is delegated to Postgres (order=created_at.asc,id.asc)
so the client never parses timestamps, and later rows simply overwrite
earlier ones per key.

payload is spread before the core fields, not after, so a tampered payload
cannot override checked/item/day."
```

---

### Task 2: `weekly_refresh.py` 배선 교체

**Files:**
- Modify: `src/routine-jammy/weekly_refresh.py`
- Modify: `tests/test_weekly_refresh.py`

**Interfaces:**
- Consumes: `supabase_client.fetch_week` (Task 1)

- [ ] **Step 1: 현재 상태 확인**

Run: `grep -n "sheet_client\|fetch_week" src/routine-jammy/weekly_refresh.py`
Expected: 3곳 — import(24행), `run()`의 기본 인자(72행), 호출(83행)

- [ ] **Step 2: import 교체**

`weekly_refresh.py`의 `from sheet_client import fetch_week` 를 다음으로 바꾼다:

```python
from supabase_client import fetch_week
```

`run()`의 `fetch_week_fn=fetch_week` 기본값과 `fetch_week_fn(week_id, person=person_id)` 호출부는 **그대로 둔다** — 시그니처가 같기 때문이다.

- [ ] **Step 3: 배선 검증 테스트 추가**

`tests/test_weekly_refresh.py` 끝에 붙인다:

```python
def test_default_fetch_is_the_supabase_client():
    """저장소 교체 후에도 run()의 기본 fetch가 실제 클라이언트를 가리키는지 고정한다."""
    import inspect

    import supabase_client
    from weekly_refresh import run

    default = inspect.signature(run).parameters["fetch_week_fn"].default
    assert default is supabase_client.fetch_week
    assert "person" in inspect.signature(default).parameters
```

- [ ] **Step 4: 전체 스위트**

Run: `python3 -m pytest tests/ -q`
Expected: 실패 0

- [ ] **Step 5: 실경로 확인 (네트워크 사용, 읽기 전용)**

```bash
cd ~/dev-out/routine-jammy && set -a && source .env && set +a
python3 -c "
import sys; sys.path.insert(0, 'src/routine-jammy')
from supabase_client import fetch_week
d = fetch_week('2026-W31', person='jammy')
print('responses:', len(d['responses']), 'reflection:', d['reflection'])
"
```
Expected: 오류 없이 `responses: 0 reflection: {}` (테이블이 비어 있으므로)

- [ ] **Step 6: 커밋**

```bash
git add src/routine-jammy/weekly_refresh.py tests/test_weekly_refresh.py
git commit -m "refactor: point the weekly refresh at Supabase

Only the import changes - supabase_client.fetch_week keeps the same
signature and return shape, so run()'s default argument and call site are
untouched. A test pins the wiring so a future swap can't silently leave
the default pointing somewhere else."
```

---

### Task 3: `health_check.py` — 무료 티어 일시정지 방지

**Files:**
- Create: `src/routine-jammy/health_check.py`
- Create: 테스트는 `tests/test_health_check.py`

**Interfaces:**
- Produces: `health_check.ping() -> int` (행 수), `health_check.main()`

**왜 필요한가**: 무료 플랜은 7일간 DB 활동이 부족하면 프로젝트를 일시정지한다. 정지되면 읽기·쓰기가 모두 막히고 **주간 리프레시가 실패한다** — 가장 필요한 순간에 죽는다. 실사용이 있으면 자연히 해결되지만 며칠 안 쓰는 기간을 메우기 위해 매일 가벼운 쿼리를 날린다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
import pytest
from health_check import ping


def test_ping_returns_row_count(monkeypatch):
    class FakeResponse:
        status_code = 200
        def json(self):
            return [{"id": 1}]

    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setattr("health_check.requests.get", lambda *a, **k: FakeResponse())
    assert ping() == 1


def test_ping_raises_on_error(monkeypatch):
    class FakeResponse:
        status_code = 503
        text = "paused"
        def json(self):
            return {}

    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setattr("health_check.requests.get", lambda *a, **k: FakeResponse())
    with pytest.raises(RuntimeError, match="503"):
        ping()
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_health_check.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

```python
"""Supabase 무료 티어 일시정지 방지용 일일 keepalive.

무료 플랜은 7일간 DB 활동이 부족하면 프로젝트를 정지시킨다. 주간 크론(7일에 한 번)만으로는
경계선에 걸리고, 정지되면 하필 그 주간 리프레시가 실패한다. 그래서 매일 가장 싼 쿼리를
한 번 날린다.

주간 리프레시와 별도 크론 엔트리로 돈다 — 주간 작업이 실패해도 이것까지 같이 죽으면 안 된다.
실패는 조용히 넘기지 않는다: 실패했다는 것은 이미 정지됐거나 곧 정지된다는 신호다.
"""

import os
import sys

import requests

from telegram_notifier import send_telegram

_TIMEOUT = 15


def ping() -> int:
    """가장 싼 쿼리 1회. 성공하면 반환된 행 수를 낸다."""
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SECRET_KEY"]
    response = requests.get(
        f"{base_url}/rest/v1/checkins",
        params={"select": "id", "limit": 1},
        headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
        timeout=_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Supabase health check failed with status {response.status_code}: {response.text}"
        )
    return len(response.json())


def main() -> None:
    try:
        ping()
    except Exception as error:
        message = (
            "Supabase health check 실패 — 프로젝트가 일시정지됐거나 곧 정지될 수 있습니다.\n"
            f"{error}\n"
            "대시보드에서 Restore project가 필요한지 확인하세요."
        )
        try:
            send_telegram(message)
        except Exception as notify_error:
            print(f"Telegram notification failed: {notify_error}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_health_check.py -q`
Expected: 2 passed

- [ ] **Step 5: 실경로 1회 실행**

```bash
cd ~/dev-out/routine-jammy && set -a && source .env && set +a
python3 src/routine-jammy/health_check.py && echo "health check OK"
```
Expected: 오류 없이 `health check OK`

- [ ] **Step 6: 크론 엔트리 추가**

`crontab -e`로 아래 한 줄을 추가한다(기존 일요일 엔트리는 **그대로 둔다**):

```
# routine-jammy — Supabase 일시정지 방지 (매일 07:00 KST)
0 7 * * * cd /home/rainny/dev-out/routine-jammy && /usr/bin/env bash -lc 'source .env 2>/dev/null; python3 src/routine-jammy/health_check.py' >> /home/rainny/dev-out/routine-jammy/logs/health-check.log 2>&1
```

확인: `crontab -l | grep -c routine-jammy` → **2**

- [ ] **Step 7: 커밋**

```bash
git add src/routine-jammy/health_check.py tests/test_health_check.py
git commit -m "feat: add daily Supabase keepalive

The free tier pauses a project after about a week of low activity, and the
weekly refresh is exactly what breaks when that happens. Real daily use
prevents it on its own; this covers the quiet stretches.

Runs as its own cron entry so a failing weekly job doesn't take it down
with it, and it alerts on failure rather than exiting quietly - a failure
here means the project is already paused or about to be."
```

---

### Task 4: 프론트 — PostgREST로 POST

**Files:**
- Modify: `docs/app.js`
- Modify: `docs/config.js`

**Interfaces:**
- Consumes: `supabase/schema.sql`의 `checkins` 테이블, `x-routine-token` 헤더 규약

**핵심 주의사항 3가지:**
1. **`Prefer: return=minimal` 필수.** `anon`에 SELECT 권한이 없어 결과를 돌려받으려 하면 `RETURNING`이 거부되어 **INSERT 전체가 실패**한다. 안전한 실패지만 "Supabase가 고장났다"로 오인하기 쉽다.
2. **토큰은 URL에서 읽는다** (`?t=...`). 저장소에 커밋하지 않는다.
3. **`note`/`reflection`은 `payload`로 감싼다.** 테이블에 그런 컬럼이 없다.

- [ ] **Step 1: `docs/config.js` 교체**

```javascript
// Supabase 연결 정보.
// publishable 키는 클라이언트에 노출되는 것을 전제로 설계된 키다 — 커밋해도 된다.
// 실제 접근 통제는 DB의 Row Level Security가 서버에서 한다.
// 사람별 쓰기 토큰은 여기 두지 않는다 — URL의 ?t= 로 전달된다.
window.ROUTINE_CONFIG = {
  supabaseUrl: 'https://wkumpxccryqjkgdhwjyb.supabase.co',
  publishableKey: 'sb_publishable_sCgRLsZ5rhY32D8dJj3PKw_GPG7gyfO',
};
```

- [ ] **Step 2: `docs/app.js`의 CONFIG 블록 교체**

파일 맨 앞 `const CONFIG = {...}` 를 다음으로 바꾼다:

```javascript
  const params = new URLSearchParams(location.search);
  const CONFIG = {
    supabaseUrl: window.ROUTINE_CONFIG && window.ROUTINE_CONFIG.supabaseUrl,
    publishableKey: window.ROUTINE_CONFIG && window.ROUTINE_CONFIG.publishableKey,
    personId: params.get('person') || 'jammy',
    writeToken: params.get('t') || '',
  };
```

- [ ] **Step 3: `postCheckin` 교체**

```javascript
  // 체크인 payload를 테이블 컬럼 모양으로 바꾼다.
  // note / reflection 은 별도 컬럼이 아니라 payload JSONB 안으로 들어간다.
  function toRow(payload) {
    const extra = {};
    if (payload.note !== undefined) extra.note = payload.note;
    if (payload.reflection !== undefined) Object.assign(extra, payload.reflection);
    return {
      person_id: CONFIG.personId,
      week_id: payload.weekId,
      day: payload.day,
      item: payload.item,
      checked: payload.checked,
      payload: extra,
      client_ts: payload.timestamp,
    };
  }

  async function postCheckin(payload) {
    const response = await fetch(`${CONFIG.supabaseUrl}/rest/v1/checkins`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        apikey: CONFIG.publishableKey,
        Authorization: `Bearer ${CONFIG.publishableKey}`,
        'x-routine-token': CONFIG.writeToken,
        // anon에 SELECT 권한이 없다. 결과를 돌려달라고 하면 INSERT 전체가 실패한다.
        Prefer: 'return=minimal',
      },
      body: JSON.stringify(toRow(payload)),
    });
    if (!response.ok) throw new Error(`status ${response.status}`);
  }
```

- [ ] **Step 4: 연결 가드 교체**

`sendCheckin`과 `flushQueue`의 `if (!CONFIG.appsScriptUrl)` 두 곳을 다음으로 바꾼다:

```javascript
    if (!CONFIG.supabaseUrl || !CONFIG.writeToken) {
```

`sendCheckin`은 그대로 큐에 넣고 반환, `flushQueue`는 그대로 반환한다. **토큰이 없으면 서버가 어차피 거부하므로 큐에 쌓아두는 편이 낫다.**

- [ ] **Step 5: 설정 화면 표시 문구 갱신**

`docs/app.js`에서 `동기화 서버 연결` 문구가 있는 줄을 찾아 조건을 바꾼다:

`docs/app.js` 289행이 다음과 같다:

```javascript
      <p class="muted">동기화 서버 연결: ${CONFIG.appsScriptUrl ? '연결됨' : '아직 설정되지 않음'}</p>
```

다음으로 바꾼다:

```javascript
      <p class="muted">동기화 서버 연결: ${CONFIG.supabaseUrl && CONFIG.writeToken ? '연결됨' : '아직 설정되지 않음 (링크에 토큰이 없습니다)'}</p>
```

- [ ] **Step 6: 옛 참조가 남지 않았는지 확인**

Run: `grep -n "appsScriptUrl\|sharedSecret" docs/`
Expected: 출력 없음

- [ ] **Step 7: JS 테스트**

Run: `node --test tests/js/`
Expected: 통과 (이 파일들은 `routine-logic.js`만 테스트하므로 영향 없음)

- [ ] **Step 8: 실제 왕복 확인**

```bash
cd ~/dev-out/routine-jammy/docs && python3 -m http.server 8899
```

브라우저에서 **`http://localhost:8899/?person=jammy&t=<토큰>`** 을 연다(토큰은 `.env`의 `ROUTINE_JAMMY_TOKEN`).

- [ ] 설정 화면에 "연결됨"이 뜬다
- [ ] 오늘 항목 하나를 체크한다
- [ ] 아래로 DB에 도달했는지 확인:

```bash
cd ~/dev-out/routine-jammy && set -a && source .env && set +a
curl -sS -H "apikey: $SUPABASE_SECRET_KEY" \
  "$SUPABASE_URL/rest/v1/checkins?select=day,item,checked,payload&order=id.desc&limit=3"
```
Expected: 방금 체크한 행이 보인다

- [ ] **토큰 없이 열었을 때 막히는지도 확인**: `http://localhost:8899/?person=jammy` (t 없음)로 열어 체크 → DB에 새 행이 **추가되지 않아야** 한다

- [ ] **Step 9: 커밋**

```bash
git add docs/app.js docs/config.js
git commit -m "feat: send check-ins to Supabase instead of Apps Script

The write token comes from the URL rather than the repo, so the publishable
key is the only credential committed - and it is designed to be public,
with RLS doing the actual enforcement server-side.

note and reflection move into the payload column since the table has no
such columns. Prefer: return=minimal is required: anon has no SELECT grant,
so asking for the inserted row back makes the whole INSERT fail."
```

---

### Task 5: 시트 잔재 제거

**Files:**
- Delete: `src/routine-jammy/sheet_client.py`, `tests/test_sheet_client.py`, `apps-script/` 전체, `specs/plans/2026-07-31-sheet-migration-runbook.md`
- Modify: `CLAUDE.md`, `.claude/skills/weekly-routine-refresh/SKILL.md`

(`.env.example`은 이 저장소에 없다 — 만들지 않는다.)

- [ ] **Step 1: 참조가 남았는지 먼저 확인**

Run: `grep -rn "sheet_client\|Apps Script\|appsScriptUrl\|ROUTINE_APPS_SCRIPT_URL\|ROUTINE_SHARED_SECRET" --include="*.py" --include="*.js" --include="*.md" . | grep -v "^./specs/2026-07-31-supabase" | grep -v "^./specs/plans/2026-08-01"`

이 목록이 이번 Task에서 고칠 대상이다. 설계 스펙과 이 계획서의 언급은 **역사 기록이므로 남긴다.**

- [ ] **Step 2: 삭제**

```bash
git rm -r apps-script
git rm src/routine-jammy/sheet_client.py tests/test_sheet_client.py
git rm specs/plans/2026-07-31-sheet-migration-runbook.md
```

- [ ] **Step 3: 전체 스위트 — 삭제로 깨진 곳이 있는지**

Run: `python3 -m pytest tests/ -q`
Expected: 실패 0. `test_sheet_client.py`에 5개가 있었으므로 총 개수가 **정확히 5 줄어든다.**
5보다 많이 줄었다면 다른 것을 망가뜨린 것이다 — 멈추고 원인을 찾을 것.

- [ ] **Step 4: `CLAUDE.md` 갱신**

Tech Stack 표의 데이터 동기화 행을 다음으로 바꾼다:

```markdown
| 데이터 동기화 | Supabase (Postgres + PostgREST). 공개 키는 RLS 하에 INSERT만, 서버는 secret 키로 읽는다 |
```

Authentication 절의 Apps Script 관련 서술을 다음으로 바꾼다:

```markdown
- **Supabase**: publishable 키는 `docs/config.js`에 커밋한다(공개 전제 키). secret 키와
  사람별 쓰기 토큰은 `.env`에만 두고 커밋하지 않는다. 접근 통제는 DB의 RLS가 한다 —
  스키마는 `supabase/schema.sql`, 근거는 `specs/2026-07-31-supabase-storage-design.md`.
```

- [ ] **Step 5: SKILL.md 갱신 — 4곳**

`.claude/skills/weekly-routine-refresh/SKILL.md`에 시트 시절 참조가 4곳 있다.
**마지막 것이 특히 중요하다 — 방금 삭제한 파일을 가리킨다.**

26행:
```bash
source .env 2>/dev/null || true   # ROUTINE_APPS_SCRIPT_URL / ROUTINE_SHARED_SECRET / ROUTINE_TELEGRAM_* 로드
```
→
```bash
source .env 2>/dev/null || true   # SUPABASE_URL / SUPABASE_SECRET_KEY / ROUTINE_TELEGRAM_* 로드
```

33행: `2. Apps Script GET으로 그 주의 체크인 데이터를 가져온다.`
→ `2. Supabase에서 그 주의 체크인 데이터를 가져온다.`

58행: `- **\`run()\` 내부에서 실패** (예: Apps Script가 응답하지 않는 \`SheetClientError\`, 배포가 아직`
→ `- **\`run()\` 내부에서 실패** (예: Supabase가 응답하지 않는 \`SupabaseClientError\`, 배포가 아직`

71행: `실패 알림을 받으면 \`apps-script/README.md\`의 배포 상태를 확인한다.`
→ `실패 알림을 받으면 Supabase 대시보드에서 프로젝트가 일시정지되지 않았는지 먼저 확인한다 (무료 티어는 활동이 없으면 정지된다).`

확인: `grep -c "Apps Script\|apps-script\|SheetClientError\|ROUTINE_APPS_SCRIPT_URL\|ROUTINE_SHARED_SECRET" .claude/skills/weekly-routine-refresh/SKILL.md` → **0**

- [ ] **Step 6: 커밋**

```bash
git add -A
git commit -m "chore: remove the Google Sheets integration

The spreadsheet was never created and no data ever reached it, so nothing
is being migrated - this is deleting an integration that was configured
but never active.

Kept: the design spec's account of why it was replaced, since that
reasoning is the record of a real security problem."
```

---

### Task 6: RLS 검증 정식화

**Files:**
- Create: `tests/test_rls_live.py`
- Modify: `pytest.ini` 또는 `pyproject.toml`(마커 등록)

**왜 필요한가**: RLS 검증 11가지를 셸에서 수동으로 돌렸을 뿐이라 재실행이 안 된다. RLS는 이 설계의 유일한 보안 경계이므로, 스키마를 고칠 때마다 다시 돌릴 수 있어야 한다.

- [ ] **Step 1: 마커 등록**

`pyproject.toml`이 없으므로 `pytest.ini`를 만든다:

```ini
[pytest]
markers =
    network: 실제 Supabase에 요청한다. 기본 실행에서 제외되며 -m network 로만 돈다.
addopts = -m "not network"
```

- [ ] **Step 2: 검증 테스트 작성**

```python
"""RLS가 실제로 막는지 살아있는 Supabase에 대고 확인한다.

RLS는 이 설계의 유일한 보안 경계다. "정책을 안 만들어서 막힌다"는 방식이 정말 막는지
확인 없이 믿지 않는다.

실행: python3 -m pytest tests/test_rls_live.py -m network -v
필요: .env의 SUPABASE_URL, SUPABASE_SECRET_KEY, ROUTINE_JAMMY_TOKEN
"""

import os

import pytest
import requests

pytestmark = pytest.mark.network

PUBLISHABLE = "sb_publishable_sCgRLsZ5rhY32D8dJj3PKw_GPG7gyfO"
TEST_WEEK = "9999-W99"          # 실데이터와 절대 겹치지 않는 주차
TIMEOUT = 20


def _env(name):
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} 이 없어 건너뜀 (set -a; source .env; set +a 후 실행)")
    return value


@pytest.fixture
def url():
    return _env("SUPABASE_URL").rstrip("/") + "/rest/v1"


@pytest.fixture
def secret():
    return _env("SUPABASE_SECRET_KEY")


@pytest.fixture
def token():
    return _env("ROUTINE_JAMMY_TOKEN")


@pytest.fixture(autouse=True)
def cleanup(url, secret):
    """테스트가 넣은 행을 반드시 지운다."""
    yield
    requests.delete(
        f"{url}/checkins",
        params={"week_id": f"eq.{TEST_WEEK}"},
        headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
        timeout=TIMEOUT,
    )


def _row(person_id="jammy", day="월", item="검증"):
    return {
        "person_id": person_id, "week_id": TEST_WEEK, "day": day,
        "item": item, "checked": True, "payload": {},
    }


def _pub_headers(token=None):
    headers = {
        "apikey": PUBLISHABLE,
        "Authorization": f"Bearer {PUBLISHABLE}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    if token is not None:
        headers["x-routine-token"] = token
    return headers


def test_publishable_cannot_select(url):
    r = requests.get(f"{url}/checkins", params={"select": "*"},
                     headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400, "공개 키로 데이터를 읽을 수 있다"


def test_publishable_cannot_update(url):
    r = requests.patch(f"{url}/checkins", params={"id": "eq.1"},
                       json={"checked": False}, headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400


def test_publishable_cannot_delete(url):
    r = requests.delete(f"{url}/checkins", params={"id": "eq.1"},
                        headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400


def test_insert_without_token_is_denied(url):
    r = requests.post(f"{url}/checkins", json=_row(), headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400, "토큰 없이 삽입할 수 있다 — 익명 쓰기·DoS 가능"


def test_insert_with_wrong_token_is_denied(url):
    r = requests.post(f"{url}/checkins", json=_row(),
                      headers=_pub_headers("definitely-not-a-real-token"), timeout=TIMEOUT)
    assert r.status_code >= 400


def test_insert_with_own_token_succeeds(url, token):
    r = requests.post(f"{url}/checkins", json=_row(),
                      headers=_pub_headers(token), timeout=TIMEOUT)
    assert r.status_code < 300, f"정상 경로가 막혔다: {r.status_code} {r.text}"


def test_cannot_insert_as_another_person(url, token):
    """이 설계의 핵심 검사.

    with check (true) 였다면 이게 성공했을 것이고, 그건 곧 누구나 남의 이름으로 기록을
    남길 수 있다는 뜻이다 — 회고 텍스트는 공개 저장소에 커밋된다.
    """
    r = requests.post(f"{url}/checkins", json=_row(person_id="someone-else"),
                      headers=_pub_headers(token), timeout=TIMEOUT)
    assert r.status_code >= 400, "자기 토큰으로 남의 person_id를 사칭할 수 있다"


def test_cannot_forge_created_at(url, token):
    """created_at은 '최신 승자' 판정 기준이므로 클라이언트가 정할 수 없어야 한다."""
    row = {**_row(day="화"), "created_at": "2099-01-01T00:00:00Z"}
    r = requests.post(f"{url}/checkins", json=row,
                      headers=_pub_headers(token), timeout=TIMEOUT)
    assert r.status_code >= 400, "created_at을 클라이언트가 지정할 수 있다"


def test_oversized_payload_is_rejected(url, token):
    row = {**_row(day="수"), "payload": {"n": "x" * 6000}}
    r = requests.post(f"{url}/checkins", json=row,
                      headers=_pub_headers(token), timeout=TIMEOUT)
    assert r.status_code >= 400


def test_publishable_cannot_enumerate_tokens(url):
    r = requests.get(f"{url}/person_write_tokens", params={"select": "*"},
                     headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400, "공개 키로 토큰 목록을 읽을 수 있다"


def test_secret_key_can_read(url, secret):
    r = requests.get(f"{url}/checkins", params={"select": "*", "limit": 1},
                     headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
                     timeout=TIMEOUT)
    assert r.status_code == 200, "크론이 읽지 못한다"
```

- [ ] **Step 3: 기본 스위트에서 제외되는지 확인**

Run: `python3 -m pytest tests/ -q`
Expected: 실패 0. **네트워크 테스트가 실행되지 않는다**(마커로 제외됨).

- [ ] **Step 4: 네트워크 검증 실행**

```bash
cd ~/dev-out/routine-jammy && set -a && source .env && set +a
python3 -m pytest tests/test_rls_live.py -m network -v
```
Expected: 11 passed

- [ ] **Step 5: 정리가 실제로 됐는지**

```bash
cd ~/dev-out/routine-jammy && set -a && source .env && set +a
curl -sS -H "apikey: $SUPABASE_SECRET_KEY" \
  "$SUPABASE_URL/rest/v1/checkins?week_id=eq.9999-W99&select=id"
```
Expected: `[]`

- [ ] **Step 6: 커밋**

```bash
git add tests/test_rls_live.py pytest.ini
git commit -m "test: formalize the RLS verification as runnable tests

These were run once by hand in a shell, which means they could not be
re-run after a schema change. RLS is the only security boundary here, so
the checks need to be repeatable.

Marked as network and excluded from the default suite; run with
-m network. The impersonation case is the one that matters most - it is
exactly what the original with-check-true policy would have allowed."
```

---

## 완료 기준

- [ ] `python3 -m pytest tests/ -q` 실패 0
- [ ] `python3 -m pytest tests/test_rls_live.py -m network -v` 11 passed
- [ ] `grep -rn "sheet_client\|appsScriptUrl" src/ docs/ tests/` 출력 없음
- [ ] 브라우저에서 토큰 있는 링크로 체크 → DB에 행이 생긴다
- [ ] 토큰 없는 링크로 체크 → DB에 행이 생기지 않는다
- [ ] `crontab -l | grep -c routine-jammy` → 2 (주간 + 일일)
- [ ] `git status`에 `.env`가 나타나지 않는다

## 이 계획 이후

- 배우자 폰에서 **토큰이 포함된 새 링크**로 홈화면 재추가 (기존 아이콘은 토큰이 없어 동작하지 않는다)
- 대화 기록에 남은 secret 키와 쓰기 토큰 회전 (`scripts/set-supabase-secret.sh`, 토큰은 `revoked_at` 후 재발급)
- 스펙 4~7단계(프론트 라우팅·테마·장식 슬롯·크론 다중 사용자 루프)는 별도 계획
