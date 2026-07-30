# routine-jammy 다중 사용자 백엔드 구현 계획 (스펙 1~3단계)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 배우자(jammy) 전용으로 하드코딩된 루틴 백엔드를 아이템 카탈로그 + 사람별 설정 구조로 바꾸고, 시트에 `person` 차원을 추가한다 — jammy의 화면 동작은 조금도 변하지 않은 채로.

**Architecture:** 3곳에 흩어진 하드코딩 아이템 목록(`routine_rules.CATEGORIES`, `exercise_stats.EXERCISE_CATEGORIES`, `history_store._MEAL_ITEMS`)을 단일 `catalog.json`으로 통합하고, 각 아이템에 `ruleType`을 부여해 조정 규칙을 데이터로 만든다. 사람별 설정은 `people/<personId>.json`, 데이터는 `docs/data/<personId>/`·`history/<personId>/`로 분리한다. Apps Script는 배포 1개·시트 1개를 유지한 채 `person` 컬럼으로 네임스페이스를 나눈다.

**Tech Stack:** Python 3.12 (표준 라이브러리 + `requests`), pytest, Google Apps Script.

## Global Constraints

- **C-1 (하드 제약)**: jammy의 완료율·운동 연속일수·리포트 탭·주간 이력 값이 마이그레이션 전후로 동일해야 한다. 충돌 시 **기존 사용자 UI 동일성 > 새 기능**.
- 카탈로그 아이템 `id`는 **현재 한글 문자열 그대로** 사용한다 (`"슬로우 조깅"` 등). 시트 기존 행의 `item` 값이 이 문자열이라, 새 id를 만들면 과거 이력과 조인되지 않는다.
- `jammy`의 `personId`는 **`jammy`** 로 고정하며 이후 변경하지 않는다 (이력 조인 키).
- 조정 판정 임계값·관측 창은 현행 유지: `binaryCheck`/`timedPractice`는 **주당 완료율 50% 미만이 2주 연속**, `logging`은 **주당 기록 3일 미만이 2주 연속**. 두 경우 모두 **각 주를 독립적으로 판정**한다(2주 합산이 아니다).
- Apps Script 웹앱 **배포는 1개, 스프레드시트도 1개**를 유지한다. 사람마다 배포/시트를 나누지 않는다.
- 테스트 실행: 저장소 루트에서 `python3 -m pytest tests/ -q`. `tests/conftest.py`가 `src/routine-jammy`를 `sys.path`에 넣어주므로 모듈은 `from routine_rules import ...` 형태로 임포트한다.
- 커밋 메시지는 한 줄 요약 + 필요 시 본문. 기존 관행을 따른다.

## 이 계획이 다루지 않는 것

스펙 4~7단계(프론트 라우팅·히어로 테마·장식 슬롯·크론 루프화·신규 사용자 온보딩)는 **별도 계획**으로 뺀다. 이 계획의 종료 상태는 "jammy가 똑같이 동작하면서 백엔드가 다중 사용자 구조를 갖춘 상태"다.

## 착수 전 확인된 사실

- 앱 최초 배포 2026-07-26, 현재 주차 2026-W31 → **시트 데이터는 최대 1~2주치(약 60~130행)**. 마이그레이션에 배치/재시도 설계가 필요 없다. (스펙 OQ-3 해결)
- `history/` 디렉터리는 **비어 있다** — 주간 리프레시가 아직 한 번도 완주하지 않았다. 따라서 `history/data.json` 이전 작업은 없고, 새 경로에 처음부터 쓰면 된다.
- 현재 테스트 64개 전부 통과 상태다. 이 계획의 모든 단계에서 이 숫자는 줄어들면 안 된다.

## 스펙 대비 추가 발견 (계획에 포함)

스펙 작성 시 파악되지 않았던 것들로, 빠뜨리면 실제로 깨진다:

1. **하드코딩 아이템 목록이 3곳이다.** 스펙은 `routine_rules.py`만 언급했으나 `exercise_stats.EXERCISE_CATEGORIES`(운동 연속일수 계산)와 `history_store._MEAL_ITEMS`(식단 추출)도 하드코딩되어 있다. → Task 5
2. **Apps Script 중복 판정 키가 사람을 구분하지 않는다.** `doPost`가 `(weekId, day, item)`으로 기존 행을 찾아 덮어쓴다. `person`을 키에 넣지 않으면 **두 사람의 같은 요일·같은 아이템 체크인이 서로를 덮어쓴다.** 회고 시트도 `(weekId)`만 보므로 동일 문제. → Task 9
3. **회고(Reflections) 시트에도 `person`이 필요하다.** 스펙은 "체크인 행"만 언급했다. → Task 9
4. **프론트가 `person`을 보내기 전에 필터를 켜면 jammy 체크인이 깨진다.** 프론트 변경은 4단계(별도 계획)이므로, Apps Script가 `person` 누락 시 기본값 `jammy`로 처리해 하위 호환을 유지한다. → Task 9

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `catalog.json` (신규, 루트) | 선택 가능한 루틴 아이템 마스터 목록 (id/label/group/ruleType/suggestion) |
| `people/jammy.json` (신규) | jammy의 사람 설정 (선택 아이템, 테마, 활성 여부) |
| `src/routine-jammy/catalog.py` (신규) | 카탈로그 로드·검증·조회. 다른 모듈은 여기를 통해서만 아이템을 안다 |
| `src/routine-jammy/person.py` (신규) | 사람 설정 로드·검증. 카탈로그에 없는 아이템 참조를 거부 |
| `src/routine-jammy/routine_rules.py` (수정) | 카탈로그 기반 완료율·조정 판정. `logging` 규칙 추가 |
| `src/routine-jammy/exercise_stats.py` (수정) | `EXERCISE_CATEGORIES` 제거, 운동 아이템을 인자로 받음 |
| `src/routine-jammy/history_store.py` (수정) | `_MEAL_ITEMS` 제거, 식단 아이템을 인자로 받음 |
| `src/routine-jammy/sheet_client.py` (수정) | `person` 파라미터 추가 |
| `src/routine-jammy/weekly_refresh.py` (수정) | 사람별 경로·아이템으로 동작 |
| `apps-script/Code.gs` (수정) | `person` 컬럼 읽기/쓰기, 중복 판정 키에 person 포함, 조회 필터 |
| `apps-script/migrate-person-column.gs` (신규) | 1회용 마이그레이션 함수 |
| `tests/test_characterization.py` (신규) | 리팩터 전 현재 동작을 고정하는 안전망 |
| `tests/test_catalog.py`, `tests/test_person.py` (신규) | 신규 모듈 테스트 |

---

### Task 1: 현재 동작을 고정하는 특성화 테스트

리팩터 중 C-1이 깨지는 것을 즉시 잡기 위한 안전망을 **먼저** 만든다. 이 테스트는 리팩터가 끝날 때까지 계속 초록이어야 한다.

**Files:**
- Create: `tests/test_characterization.py`

**Interfaces:**
- Consumes: 현재의 `routine_rules.completion_by_category/find_low_categories/suggest_adjustments`, `exercise_stats.days_with_any_exercise`, `history_store.extract_meal_log`
- Produces: 이후 모든 Task가 깨뜨리면 안 되는 기준선

- [ ] **Step 1: 특성화 테스트 작성**

```python
"""jammy의 현재 동작을 고정한다. 다중 사용자 리팩터가 이 값들을 바꾸면 C-1 위반이다.

이 파일은 리팩터 도중 시그니처가 바뀌면 함께 수정하되, **기대값(assert 우변)은 절대
바꾸지 않는다**. 기대값이 바뀌어야 통과한다면 그것은 회귀다.
"""

from exercise_stats import build_day_level, days_with_any_exercise
from history_store import extract_meal_log
from routine_rules import completion_by_category, find_low_categories, suggest_adjustments

JAMMY_WEEK_RESPONSES = [
    {"day": "월", "item": "슬로우 조깅", "checked": True},
    {"day": "화", "item": "슬로우 조깅", "checked": True},
    {"day": "수", "item": "슬로우 조깅", "checked": False},
    {"day": "월", "item": "스쿼트", "checked": True},
    {"day": "월", "item": "데드리프트", "checked": False},
    {"day": "월", "item": "런지", "checked": True},
    {"day": "월", "item": "플랭크", "checked": True},
    {"day": "월", "item": "간식섭취", "checked": True},
    {"day": "월", "item": "바이올린", "checked": False},
    {"day": "월", "item": "아점", "checked": True, "note": "달걀 2 + 그릭요거트"},
    {"day": "월", "item": "저녁", "checked": True, "note": "닭가슴살 100g"},
    {"day": "화", "item": "아점", "checked": True, "note": "두부 200g"},
]


def test_completion_rates_cover_exactly_the_seven_tracked_items():
    rates = completion_by_category(JAMMY_WEEK_RESPONSES)
    assert set(rates) == {
        "슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크", "간식섭취", "바이올린",
    }


def test_completion_rates_exact_values():
    rates = completion_by_category(JAMMY_WEEK_RESPONSES)
    assert rates["슬로우 조깅"] == round(2 / 7, 2)
    assert rates["스쿼트"] == round(1 / 7, 2)
    assert rates["데드리프트"] == 0.0
    assert rates["바이올린"] == 0.0


def test_meal_items_are_not_in_completion_rates():
    rates = completion_by_category(JAMMY_WEEK_RESPONSES)
    assert "아점" not in rates
    assert "저녁" not in rates


def test_two_consecutive_low_weeks_trigger_adjustment():
    current = {"바이올린": 0.3, "슬로우 조깅": 0.9}
    previous = {"바이올린": 0.4, "슬로우 조깅": 0.8}
    assert find_low_categories(current, previous) == ["바이올린"]


def test_single_low_week_does_not_trigger():
    current = {"바이올린": 0.3}
    previous = {"바이올린": 0.8}
    assert find_low_categories(current, previous) == []


def test_only_violin_and_snack_have_suggestion_text():
    assert suggest_adjustments(["바이올린"]) == [
        "바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안"
    ]
    assert suggest_adjustments(["간식섭취"]) == [
        "간식섭취 체크 기준을 더 쉽게 낮추는 걸 제안"
    ]
    assert suggest_adjustments(["슬로우 조깅", "스쿼트", "플랭크"]) == []


def test_exercise_day_count_ignores_non_exercise_items():
    day_level = build_day_level(JAMMY_WEEK_RESPONSES)
    assert days_with_any_exercise(day_level) == 2


def test_meal_log_extraction():
    meals = extract_meal_log(JAMMY_WEEK_RESPONSES)
    assert meals == {
        "월": {"아점": "달걀 2 + 그릭요거트", "저녁": "닭가슴살 100g"},
        "화": {"아점": "두부 200g"},
    }
```

- [ ] **Step 2: 테스트 실행 — 전부 통과해야 한다**

Run: `python3 -m pytest tests/test_characterization.py -v`
Expected: PASS (9 passed). 현재 코드의 동작을 기록하는 것이므로 처음부터 초록이다. 하나라도 실패하면 기대값이 아니라 **테스트가 틀린 것**이니 실제 동작에 맞춰 고친다.

- [ ] **Step 3: 전체 스위트 확인**

Run: `python3 -m pytest tests/ -q`
Expected: `73 passed` (기존 64 + 신규 9)

- [ ] **Step 4: 커밋**

```bash
git add tests/test_characterization.py
git commit -m "test: pin jammy's current behavior before multi-person refactor

C-1 requires the existing user's completion rates, streak counts, meal log
and adjustment suggestions to be identical after the refactor. These tests
encode the current values so any drift fails immediately."
```

---

### Task 2: 아이템 카탈로그

**Files:**
- Create: `catalog.json`
- Create: `src/routine-jammy/catalog.py`
- Create: `tests/test_catalog.py`

**Interfaces:**
- Produces:
  - `catalog.load_catalog(path: Path) -> list[dict]` — 검증된 아이템 리스트
  - `catalog.CatalogError` — 검증 실패 예외
  - `catalog.items_by_group(items, group) -> list[dict]`
  - `catalog.items_by_rule_type(items, rule_type) -> list[dict]`
  - `catalog.item_ids(items) -> list[str]`
  - `catalog.RULE_TYPES = ("binaryCheck", "timedPractice", "logging")`
  - `catalog.GROUPS = ("exercise", "meal", "other")`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
import json

import pytest
from catalog import (
    CatalogError,
    item_ids,
    items_by_group,
    items_by_rule_type,
    load_catalog,
)


def write_catalog(tmp_path, items):
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps({"schemaVersion": 1, "items": items}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_load_returns_items(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
    ])
    items = load_catalog(path)
    assert item_ids(items) == ["스쿼트"]


def test_suggestion_is_optional(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
        {"id": "바이올린", "label": "바이올린", "group": "other",
         "ruleType": "timedPractice", "suggestion": "줄이기"},
    ])
    items = load_catalog(path)
    assert items[0].get("suggestion") is None
    assert items[1]["suggestion"] == "줄이기"


def test_rejects_duplicate_id(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
        {"id": "스쿼트", "label": "스쿼트2", "group": "exercise", "ruleType": "binaryCheck"},
    ])
    with pytest.raises(CatalogError, match="중복"):
        load_catalog(path)


def test_rejects_unknown_rule_type(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "magic"},
    ])
    with pytest.raises(CatalogError, match="ruleType"):
        load_catalog(path)


def test_rejects_unknown_group(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "sport", "ruleType": "binaryCheck"},
    ])
    with pytest.raises(CatalogError, match="group"):
        load_catalog(path)


def test_rejects_missing_required_field(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
    ])
    with pytest.raises(CatalogError, match="label"):
        load_catalog(path)


def test_filters_by_group_and_rule_type(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
        {"id": "아점", "label": "아점", "group": "meal", "ruleType": "logging"},
    ])
    items = load_catalog(path)
    assert item_ids(items_by_group(items, "exercise")) == ["스쿼트"]
    assert item_ids(items_by_rule_type(items, "logging")) == ["아점"]


def test_real_catalog_contains_jammys_nine_items():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    items = load_catalog(repo_root / "catalog.json")
    assert set(item_ids(items)) >= {
        "슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크",
        "간식섭취", "바이올린", "아점", "저녁",
    }
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'catalog'`

- [ ] **Step 3: `catalog.json` 작성**

```json
{
  "schemaVersion": 1,
  "items": [
    {"id": "슬로우 조깅", "label": "슬로우 조깅", "group": "exercise", "ruleType": "binaryCheck"},
    {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
    {"id": "데드리프트", "label": "데드리프트", "group": "exercise", "ruleType": "binaryCheck"},
    {"id": "런지", "label": "런지", "group": "exercise", "ruleType": "binaryCheck"},
    {"id": "플랭크", "label": "플랭크", "group": "exercise", "ruleType": "binaryCheck"},
    {"id": "간식섭취", "label": "간식섭취", "group": "other", "ruleType": "binaryCheck",
     "suggestion": "간식섭취 체크 기준을 더 쉽게 낮추는 걸 제안"},
    {"id": "바이올린", "label": "바이올린", "group": "other", "ruleType": "timedPractice",
     "suggestion": "바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안"},
    {"id": "아점", "label": "아점", "group": "meal", "ruleType": "logging"},
    {"id": "저녁", "label": "저녁", "group": "meal", "ruleType": "logging"}
  ]
}
```

> `간식섭취`의 group이 `other`인 이유: `exercise` 그룹은 운동 연속일수 계산(Task 5)에 쓰이므로 간식 체크가 들어가면 안 된다. `meal` 그룹은 영양분석 파이프라인이 읽는 자유 텍스트 기록용이라 체크박스인 간식섭취와 성격이 다르다.

- [ ] **Step 4: `catalog.py` 구현**

```python
"""루틴 아이템 카탈로그 로드·검증·조회.

카탈로그는 '선택 가능한 루틴 아이템 종류'의 마스터 목록이다. 다른 모듈은 아이템 목록을
하드코딩하지 않고 반드시 여기를 통해 얻는다.
"""

import json
from pathlib import Path

RULE_TYPES = ("binaryCheck", "timedPractice", "logging")
GROUPS = ("exercise", "meal", "other")
_REQUIRED_FIELDS = ("id", "label", "group", "ruleType")


class CatalogError(ValueError):
    pass


def load_catalog(path: Path) -> list[dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("items")
    if not isinstance(items, list) or not items:
        raise CatalogError("catalog.json의 items가 비어 있거나 리스트가 아닙니다")

    seen = set()
    for item in items:
        for field in _REQUIRED_FIELDS:
            if not item.get(field):
                raise CatalogError(f"아이템에 필수 필드 {field}가 없습니다: {item}")
        if item["id"] in seen:
            raise CatalogError(f"중복된 아이템 id: {item['id']}")
        seen.add(item["id"])
        if item["group"] not in GROUPS:
            raise CatalogError(
                f"알 수 없는 group '{item['group']}' (허용: {', '.join(GROUPS)})"
            )
        if item["ruleType"] not in RULE_TYPES:
            raise CatalogError(
                f"알 수 없는 ruleType '{item['ruleType']}' (허용: {', '.join(RULE_TYPES)})"
            )
    return items


def item_ids(items) -> list[str]:
    return [item["id"] for item in items]


def items_by_group(items, group) -> list[dict]:
    return [item for item in items if item["group"] == group]


def items_by_rule_type(items, rule_type) -> list[dict]:
    return [item for item in items if item["ruleType"] == rule_type]
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_catalog.py -v`
Expected: PASS (8 passed)

- [ ] **Step 6: 커밋**

```bash
git add catalog.json src/routine-jammy/catalog.py tests/test_catalog.py
git commit -m "feat: add routine item catalog with rule types

Replaces the hardcoded per-person item lists with a single master catalog.
Each item carries a ruleType that decides how its weekly adjustment is
judged, so adding a person means adding data, not code.

Item ids are the existing Korean strings because the sheet's stored item
values use them - a new id scheme would orphan the check-in history."
```

---

### Task 3: `routine_rules`를 카탈로그 기반으로 전환

**Files:**
- Modify: `src/routine-jammy/routine_rules.py` (전면 재작성)
- Modify: `tests/test_routine_rules.py`
- Modify: `tests/test_characterization.py` (호출 시그니처만)

**Interfaces:**
- Consumes: `catalog.items_by_rule_type`, `catalog.item_ids`
- Produces:
  - `routine_rules.completion_by_category(responses, items) -> dict[str, float]`
  - `routine_rules.find_low_categories(current_rates, previous_rates, threshold=0.5) -> list[str]` (시그니처 불변)
  - `routine_rules.suggest_adjustments(low_ids, items) -> list[str]`
  - `routine_rules.RATE_TRACKED_RULE_TYPES = ("binaryCheck", "timedPractice")`

- [ ] **Step 1: 실패하는 테스트로 교체**

`tests/test_routine_rules.py` 전체를 아래로 바꾼다:

```python
from catalog import load_catalog
from routine_rules import (
    completion_by_category,
    find_low_categories,
    suggest_adjustments,
)

ITEMS = [
    {"id": "슬로우 조깅", "label": "슬로우 조깅", "group": "exercise", "ruleType": "binaryCheck"},
    {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
    {"id": "바이올린", "label": "바이올린", "group": "other", "ruleType": "timedPractice",
     "suggestion": "바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안"},
    {"id": "아점", "label": "아점", "group": "meal", "ruleType": "logging"},
]


def test_completion_by_category_counts_checked_days():
    responses = [
        {"day": "월", "item": "슬로우 조깅", "checked": True},
        {"day": "화", "item": "슬로우 조깅", "checked": True},
        {"day": "수", "item": "슬로우 조깅", "checked": False},
        {"day": "월", "item": "스쿼트", "checked": True},
    ]
    rates = completion_by_category(responses, ITEMS)
    assert rates["슬로우 조깅"] == round(2 / 7, 2)
    assert rates["스쿼트"] == round(1 / 7, 2)
    assert rates["바이올린"] == 0.0


def test_logging_items_are_excluded_from_rates():
    responses = [{"day": "월", "item": "아점", "checked": True, "note": "달걀"}]
    rates = completion_by_category(responses, ITEMS)
    assert "아점" not in rates


def test_unknown_item_in_responses_is_ignored():
    responses = [{"day": "월", "item": "존재하지않는아이템", "checked": True}]
    rates = completion_by_category(responses, ITEMS)
    assert "존재하지않는아이템" not in rates


def test_find_low_categories_requires_two_consecutive_weeks():
    current = {"스쿼트": 0.3, "슬로우 조깅": 0.9}
    previous = {"스쿼트": 0.4, "슬로우 조깅": 0.8}
    assert find_low_categories(current, previous) == ["스쿼트"]


def test_find_low_categories_ignores_first_week_with_no_history():
    current = {"스쿼트": 0.2}
    assert find_low_categories(current, None) == []


def test_suggest_adjustments_maps_items_with_suggestion_only():
    assert suggest_adjustments(["바이올린", "슬로우 조깅"], ITEMS) == [
        "바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안"
    ]


def test_suggest_adjustments_ignores_unknown_id():
    assert suggest_adjustments(["없는아이템"], ITEMS) == []
```

`tests/test_characterization.py`에서 두 호출을 카탈로그 인자를 받도록 고친다. **기대값은 건드리지 않는다.** 파일 상단에 추가:

```python
from pathlib import Path

from catalog import load_catalog

CATALOG = load_catalog(Path(__file__).resolve().parents[1] / "catalog.json")
```

그리고 호출부를 바꾼다:
- `completion_by_category(JAMMY_WEEK_RESPONSES)` → `completion_by_category(JAMMY_WEEK_RESPONSES, CATALOG)`
- `suggest_adjustments(["바이올린"])` → `suggest_adjustments(["바이올린"], CATALOG)`
- `suggest_adjustments(["간식섭취"])` → `suggest_adjustments(["간식섭취"], CATALOG)`
- `suggest_adjustments(["슬로우 조깅", "스쿼트", "플랭크"])` → `suggest_adjustments(["슬로우 조깅", "스쿼트", "플랭크"], CATALOG)`

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_routine_rules.py tests/test_characterization.py -v`
Expected: FAIL — `TypeError: completion_by_category() takes 1 positional argument but 2 were given`

- [ ] **Step 3: `routine_rules.py` 재작성**

```python
"""주간 체크인 채점과 루틴 조정 판정 (순수 함수).

아이템 목록은 카탈로그(catalog.py)에서 오며 이 모듈에 하드코딩하지 않는다.
`logging` 타입 아이템은 체크박스가 아니라 자유 텍스트 기록이므로 완료율 집계에서
제외되고, 별도 규칙(recorded_days_by_item / find_low_logging_items)으로 판정한다.
"""

RATE_TRACKED_RULE_TYPES = ("binaryCheck", "timedPractice")


def _rate_tracked(items):
    return [item for item in items if item["ruleType"] in RATE_TRACKED_RULE_TYPES]


def completion_by_category(responses, items):
    """items 중 완료율 추적 대상(binaryCheck/timedPractice)에 대해 주간 완료율을 낸다.

    체크된 일수 / 7 로 계산하고 소수 둘째 자리에서 반올림한다. 카탈로그에 없는 아이템이
    responses에 있으면 무시한다.
    """
    totals = {item["id"]: 0 for item in _rate_tracked(items)}
    for response in responses:
        if response["item"] in totals and response["checked"]:
            totals[response["item"]] += 1
    return {item_id: round(count / 7, 2) for item_id, count in totals.items()}


def find_low_categories(current_rates, previous_rates, threshold=0.5):
    """이번 주와 지난 주가 **각각** threshold 미만인 아이템 id를 낸다.

    2주 합산이 아니라 주 단위 독립 판정이다. 지난 주 이력이 없으면 아무것도 내지 않는다.
    """
    if not previous_rates:
        return []
    low = []
    for item_id, rate in current_rates.items():
        previous_rate = previous_rates.get(item_id)
        if rate < threshold and previous_rate is not None and previous_rate < threshold:
            low.append(item_id)
    return low


def suggest_adjustments(low_ids, items):
    """low_ids 중 카탈로그에 suggestion 문구가 있는 아이템의 문구만 낸다."""
    suggestions = {
        item["id"]: item["suggestion"] for item in items if item.get("suggestion")
    }
    return [suggestions[item_id] for item_id in low_ids if item_id in suggestions]
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_routine_rules.py tests/test_characterization.py -v`
Expected: PASS (7 + 9 = 16 passed)

- [ ] **Step 5: 전체 스위트 — 아직 깨지는 곳이 있다**

Run: `python3 -m pytest tests/ -q`
Expected: FAIL — `tests/test_weekly_refresh.py`가 옛 시그니처로 호출한다. 다음 스텝에서 고친다.

- [ ] **Step 6: `weekly_refresh.py` 호출부 임시 수정**

`weekly_refresh.py` 상단 임포트에 카탈로그를 추가한다:

```python
from pathlib import Path

from catalog import load_catalog
```

`run()` 안의 두 줄을 고친다:

```python
    catalog_items = load_catalog(Path(__file__).resolve().parents[2] / "catalog.json")
    rates = completion_by_category(sheet_data["responses"], catalog_items)
```

```python
    adjustments = suggest_adjustments(low_categories, catalog_items)
```

> Task 8에서 이 로드 로직은 사람 설정 기반으로 다시 바뀐다. 지금은 전체 스위트를 초록으로 되돌리는 최소 수정이다.

- [ ] **Step 7: 전체 스위트 통과 확인**

Run: `python3 -m pytest tests/ -q`
Expected: `81 passed` (73 + 카탈로그 8)

- [ ] **Step 8: 커밋**

```bash
git add src/routine-jammy/routine_rules.py src/routine-jammy/weekly_refresh.py tests/test_routine_rules.py tests/test_characterization.py
git commit -m "refactor: drive routine_rules from the catalog instead of hardcoded lists

completion_by_category and suggest_adjustments now take the catalog items,
so the tracked set and the suggestion text come from data. find_low_categories
is unchanged - its per-week independent evaluation was already correct.

The characterization tests still assert the same values, only the call
signatures moved."
```

---

### Task 4: `logging` 규칙 (식단 기록 판정)

**Files:**
- Modify: `src/routine-jammy/routine_rules.py`
- Modify: `tests/test_routine_rules.py`

**Interfaces:**
- Produces:
  - `routine_rules.recorded_days_by_item(responses, items) -> dict[str, int]`
  - `routine_rules.find_low_logging_items(current_counts, previous_counts, threshold=3) -> list[str]`
  - `routine_rules.LOGGING_MIN_DAYS = 3`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_routine_rules.py` 끝에 붙인다:

```python
from routine_rules import find_low_logging_items, recorded_days_by_item


def test_recorded_days_counts_days_with_nonempty_note():
    responses = [
        {"day": "월", "item": "아점", "checked": True, "note": "달걀"},
        {"day": "화", "item": "아점", "checked": True, "note": "두부"},
        {"day": "수", "item": "아점", "checked": True, "note": ""},
        {"day": "목", "item": "아점", "checked": False, "note": "무시됨"},
    ]
    assert recorded_days_by_item(responses, ITEMS) == {"아점": 2}


def test_recorded_days_counts_a_day_once_even_with_duplicate_rows():
    responses = [
        {"day": "월", "item": "아점", "checked": True, "note": "달걀"},
        {"day": "월", "item": "아점", "checked": True, "note": "달걀 수정"},
    ]
    assert recorded_days_by_item(responses, ITEMS) == {"아점": 1}


def test_recorded_days_ignores_non_logging_items():
    responses = [{"day": "월", "item": "스쿼트", "checked": True, "note": "메모"}]
    assert recorded_days_by_item(responses, ITEMS) == {"아점": 0}


def test_logging_low_requires_both_weeks_under_threshold():
    assert find_low_logging_items({"아점": 2}, {"아점": 1}) == ["아점"]


def test_logging_one_good_week_breaks_the_streak():
    assert find_low_logging_items({"아점": 2}, {"아점": 3}) == []
    assert find_low_logging_items({"아점": 5}, {"아점": 1}) == []


def test_logging_no_history_does_not_trigger():
    assert find_low_logging_items({"아점": 0}, None) == []


def test_logging_threshold_is_exclusive_at_three():
    assert find_low_logging_items({"아점": 3}, {"아점": 3}) == []
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_routine_rules.py -v`
Expected: FAIL — `ImportError: cannot import name 'recorded_days_by_item'`

- [ ] **Step 3: 구현 추가**

`routine_rules.py` 끝에 붙인다:

```python
LOGGING_MIN_DAYS = 3


def recorded_days_by_item(responses, items):
    """ruleType이 logging인 아이템에 대해, 비어있지 않은 기록이 있는 **날의 수**를 센다.

    같은 날 같은 아이템이 여러 행으로 들어와도 하루로 센다.
    """
    logging_ids = {item["id"] for item in items if item["ruleType"] == "logging"}
    days_seen = {item_id: set() for item_id in logging_ids}
    for response in responses:
        item_id = response["item"]
        if item_id not in logging_ids or not response["checked"]:
            continue
        if not response.get("note"):
            continue
        days_seen[item_id].add(response["day"])
    return {item_id: len(days) for item_id, days in days_seen.items()}


def find_low_logging_items(current_counts, previous_counts, threshold=LOGGING_MIN_DAYS):
    """이번 주와 지난 주가 **각각** threshold일 미만인 logging 아이템 id를 낸다.

    2주 합산이 아니다 — 한 주라도 threshold일 이상이면 연속이 끊긴다.
    """
    if not previous_counts:
        return []
    low = []
    for item_id, count in current_counts.items():
        previous_count = previous_counts.get(item_id)
        if count < threshold and previous_count is not None and previous_count < threshold:
            low.append(item_id)
    return low
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/test_routine_rules.py -v`
Expected: PASS (14 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/routine-jammy/routine_rules.py tests/test_routine_rules.py
git commit -m "feat: add logging ruleType for free-text records

Meal notes are textareas, not checkboxes, so they have no completion rate.
They're judged on how many days actually got a non-empty record, with the
same per-week independent evaluation the rate rules use: under 3 days in a
week, two weeks running.

Threshold is 3 rather than the rate rules' 50% (3.5 days) because writing
a record every day is harder than ticking a box, and an integer day count
leaves no rounding ambiguity."
```

---

### Task 5: `exercise_stats`·`history_store`의 하드코딩 제거

스펙이 놓쳤던 나머지 두 하드코딩 목록을 카탈로그로 옮긴다.

**Files:**
- Modify: `src/routine-jammy/exercise_stats.py`
- Modify: `src/routine-jammy/history_store.py`
- Modify: `src/routine-jammy/weekly_refresh.py`
- Modify: `tests/test_exercise_stats.py`, `tests/test_history_store.py`, `tests/test_characterization.py`

**Interfaces:**
- Produces:
  - `exercise_stats.days_with_any_exercise(day_level, exercise_ids) -> int`
  - `exercise_stats.exercised_sequence(history, week_id, day_level, exercise_ids) -> list[bool]`
  - `history_store.extract_meal_log(responses, meal_ids) -> dict`
  - `history_store.render_week_markdown(week_id, entry, meal_ids) -> str`
  - `history_store.save_week_markdown(history_dir, week_id, entry, meal_ids) -> Path`
  - `exercise_stats.DAY_ORDER` (불변, 그대로 유지)

- [ ] **Step 1: 기존 시그니처 사용처 전부 찾기**

Run: `grep -rn "EXERCISE_CATEGORIES\|_MEAL_ITEMS\|days_with_any_exercise\|exercised_sequence\|extract_meal_log\|render_week_markdown\|save_week_markdown" src tests`
Expected: `src/routine-jammy/{exercise_stats,history_store,weekly_refresh}.py`와 `tests/{test_exercise_stats,test_history_store,test_weekly_refresh,test_characterization}.py`가 나온다. 이 목록이 이번 Task에서 고칠 전부다.

- [ ] **Step 2: 테스트를 새 시그니처로 고친다**

`tests/test_exercise_stats.py`에서 `days_with_any_exercise(day_level)` 호출을 전부 `days_with_any_exercise(day_level, EXERCISE_IDS)`로, `exercised_sequence(history, week_id, day_level)`를 `exercised_sequence(history, week_id, day_level, EXERCISE_IDS)`로 바꾸고 파일 상단에 추가:

```python
EXERCISE_IDS = ["슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크"]
```

`tests/test_history_store.py`에서 `extract_meal_log(responses)` → `extract_meal_log(responses, MEAL_IDS)`, `render_week_markdown(week_id, entry)` → `render_week_markdown(week_id, entry, MEAL_IDS)`, `save_week_markdown(dir, week_id, entry)` → `save_week_markdown(dir, week_id, entry, MEAL_IDS)`로 바꾸고 상단에 추가:

```python
MEAL_IDS = ["아점", "저녁"]
```

`tests/test_characterization.py`에서도 두 곳을 고친다 (**기대값은 그대로**):

```python
from catalog import item_ids, items_by_group

EXERCISE_IDS = item_ids(items_by_group(CATALOG, "exercise"))
MEAL_IDS = item_ids(items_by_group(CATALOG, "meal"))
```

- `days_with_any_exercise(day_level)` → `days_with_any_exercise(day_level, EXERCISE_IDS)`
- `extract_meal_log(JAMMY_WEEK_RESPONSES)` → `extract_meal_log(JAMMY_WEEK_RESPONSES, MEAL_IDS)`

- [ ] **Step 3: 실패 확인**

Run: `python3 -m pytest tests/test_exercise_stats.py tests/test_history_store.py tests/test_characterization.py -q`
Expected: FAIL — `TypeError: days_with_any_exercise() takes 1 positional argument but 2 were given`

- [ ] **Step 4: `exercise_stats.py` 수정**

모듈 상단의 `EXERCISE_CATEGORIES = [...]` 줄을 **삭제**하고, `DAY_ORDER`는 남긴다. 그리고 세 함수를 고친다:

```python
def _day_has_exercise(items, exercise_ids):
    return any(items.get(item_id) for item_id in exercise_ids)


def days_with_any_exercise(day_level, exercise_ids):
    """day_level에 존재하는 날 중, exercise_ids 가운데 하나라도 True인 날의 수."""
    return sum(1 for items in day_level.values() if _day_has_exercise(items, exercise_ids))
```

`exercised_sequence`도 `exercise_ids`를 받아 내부의 `_day_has_exercise` 호출에 넘기도록 고친다. `build_day_level`과 `longest_current_streak`은 아이템 목록을 쓰지 않으므로 그대로 둔다.

- [ ] **Step 5: `history_store.py` 수정**

모듈 상단의 `_MEAL_ITEMS = ["아점", "저녁"]`을 **삭제**하고 세 함수에 `meal_ids` 파라미터를 추가한다:

```python
def extract_meal_log(responses, meal_ids):
    """{day: {item_id: note}} 를 낸다. checked=True이고 note가 비어있지 않은 행만."""
    meals = {}
    for response in responses:
        if response["item"] not in meal_ids or not response["checked"]:
            continue
        note = response.get("note")
        if not note:
            continue
        meals.setdefault(response["day"], {})[response["item"]] = note
    return meals
```

`render_week_markdown(week_id, entry, meal_ids)`의 식사 기록 절에서 `_MEAL_ITEMS`를 `meal_ids`로 바꾸고, `save_week_markdown(history_dir, week_id, entry, meal_ids)`는 `render_week_markdown`에 그대로 넘긴다.

- [ ] **Step 6: `weekly_refresh.py` 호출부 수정**

임포트에 추가:

```python
from catalog import item_ids, items_by_group
```

`run()` 안에서 카탈로그를 로드한 직후에 두 목록을 만들고, 호출부에 넘긴다:

```python
    exercise_ids = item_ids(items_by_group(catalog_items, "exercise"))
    meal_ids = item_ids(items_by_group(catalog_items, "meal"))
```

- `meals = extract_meal_log(sheet_data["responses"])` → `extract_meal_log(sheet_data["responses"], meal_ids)`
- `exercise_days = days_with_any_exercise(day_level)` → `days_with_any_exercise(day_level, exercise_ids)`
- `exercised_sequence(history, week_id, day_level)` → `exercised_sequence(history, week_id, day_level, exercise_ids)`
- `save_week_markdown(history_dir, week_id, entry)` → `save_week_markdown(history_dir, week_id, entry, meal_ids)`

- [ ] **Step 7: 전체 스위트 통과 확인**

Run: `python3 -m pytest tests/ -q`
Expected: `88 passed`

- [ ] **Step 8: 하드코딩이 정말 사라졌는지 확인**

Run: `grep -rn "슬로우 조깅\|아점\|저녁" src/routine-jammy/`
Expected: 출력 없음. 하나라도 나오면 그 파일에 아직 사람별 값이 박혀 있는 것이다.

- [ ] **Step 9: 커밋**

```bash
git add src/routine-jammy/exercise_stats.py src/routine-jammy/history_store.py src/routine-jammy/weekly_refresh.py tests/
git commit -m "refactor: remove the last two hardcoded item lists

exercise_stats.EXERCISE_CATEGORIES and history_store._MEAL_ITEMS were a
second and third copy of the per-person item list that the design doc
missed - only routine_rules was accounted for. Both now take ids derived
from the catalog's group field.

src/ no longer contains any person-specific item string."
```

---

### Task 6: 사람 설정

**Files:**
- Create: `people/jammy.json`
- Create: `src/routine-jammy/person.py`
- Create: `tests/test_person.py`

**Interfaces:**
- Consumes: `catalog.load_catalog`, `catalog.item_ids`
- Produces:
  - `person.load_person(path, catalog_items) -> dict`
  - `person.load_all_people(people_dir, catalog_items) -> list[dict]` — `personId` 오름차순, `active=False` 포함
  - `person.active_people(people) -> list[dict]`
  - `person.person_items(person, catalog_items) -> list[dict]` — 그 사람이 고른 카탈로그 아이템
  - `person.PersonError`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
import json

import pytest
from person import (
    PersonError,
    active_people,
    load_all_people,
    load_person,
    person_items,
)

CATALOG = [
    {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
    {"id": "아점", "label": "아점", "group": "meal", "ruleType": "logging"},
]


def write_person(dir_path, person_id, **overrides):
    payload = {
        "personId": person_id,
        "displayName": person_id,
        "themeId": "pastel",
        "active": True,
        "items": ["스쿼트"],
    }
    payload.update(overrides)
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / f"{person_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_person_returns_config(tmp_path):
    path = write_person(tmp_path, "jammy")
    loaded = load_person(path, CATALOG)
    assert loaded["personId"] == "jammy"
    assert loaded["themeId"] == "pastel"


def test_rejects_item_not_in_catalog(tmp_path):
    path = write_person(tmp_path, "jammy", items=["존재하지않음"])
    with pytest.raises(PersonError, match="카탈로그"):
        load_person(path, CATALOG)


def test_rejects_person_id_mismatching_filename(tmp_path):
    path = write_person(tmp_path, "jammy", personId="other")
    with pytest.raises(PersonError, match="파일명"):
        load_person(path, CATALOG)


def test_rejects_empty_items(tmp_path):
    path = write_person(tmp_path, "jammy", items=[])
    with pytest.raises(PersonError, match="items"):
        load_person(path, CATALOG)


def test_load_all_people_sorted_by_id(tmp_path):
    write_person(tmp_path, "zoe")
    write_person(tmp_path, "amy")
    people = load_all_people(tmp_path, CATALOG)
    assert [p["personId"] for p in people] == ["amy", "zoe"]


def test_active_people_filters_inactive(tmp_path):
    write_person(tmp_path, "amy")
    write_person(tmp_path, "zoe", active=False)
    people = load_all_people(tmp_path, CATALOG)
    assert [p["personId"] for p in active_people(people)] == ["amy"]


def test_person_items_returns_catalog_entries(tmp_path):
    path = write_person(tmp_path, "jammy", items=["아점", "스쿼트"])
    loaded = load_person(path, CATALOG)
    assert [i["id"] for i in person_items(loaded, CATALOG)] == ["아점", "스쿼트"]


def test_real_jammy_config_selects_all_nine_items():
    from pathlib import Path

    from catalog import load_catalog

    repo_root = Path(__file__).resolve().parents[1]
    catalog_items = load_catalog(repo_root / "catalog.json")
    loaded = load_person(repo_root / "people" / "jammy.json", catalog_items)
    assert loaded["personId"] == "jammy"
    assert loaded["themeId"] == "pastel"
    assert set(loaded["items"]) == {
        "슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크",
        "간식섭취", "바이올린", "아점", "저녁",
    }
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_person.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'person'`

- [ ] **Step 3: `people/jammy.json` 작성**

```json
{
  "personId": "jammy",
  "displayName": "재미",
  "themeId": "pastel",
  "active": true,
  "items": [
    "슬로우 조깅",
    "스쿼트",
    "데드리프트",
    "런지",
    "플랭크",
    "간식섭취",
    "바이올린",
    "아점",
    "저녁"
  ]
}
```

> `items`는 목표값 없이 id 목록만 둔다. 스펙 표에는 "아이템별 목표값"이 함께 적혀 있으나, 실제 목표값("25분 · 아주 편하게" 등)은 이미 `docs/data/current-week.json`의 `exercise.detail`에 있다. 여기에 또 두면 진실의 원천이 둘이 된다. 목표값이 정말 필요해지면 그때 `{"id": ..., "target": ...}` 형태로 확장한다.

- [ ] **Step 4: `person.py` 구현**

```python
"""사람별 루틴 설정 로드·검증.

한 사람의 루틴은 '카탈로그에서 고른 아이템 목록 + 테마'다. 카탈로그에 없는 아이템을
참조하면 로드 단계에서 거부한다 — 크론이 돌다가 조용히 빈 결과를 내는 것보다 낫다.
"""

import json
from pathlib import Path

from catalog import item_ids

_REQUIRED_FIELDS = ("personId", "displayName", "themeId", "items")


class PersonError(ValueError):
    pass


def load_person(path: Path, catalog_items) -> dict:
    path = Path(path)
    config = json.loads(path.read_text(encoding="utf-8"))

    for field in _REQUIRED_FIELDS:
        if not config.get(field):
            raise PersonError(f"{path.name}에 필수 필드 {field}가 없습니다")

    if config["personId"] != path.stem:
        raise PersonError(
            f"personId '{config['personId']}'가 파일명 '{path.stem}'과 다릅니다"
        )

    known = set(item_ids(catalog_items))
    unknown = [item_id for item_id in config["items"] if item_id not in known]
    if unknown:
        raise PersonError(f"카탈로그에 없는 아이템: {', '.join(unknown)}")

    config.setdefault("active", True)
    return config


def load_all_people(people_dir: Path, catalog_items) -> list[dict]:
    people_dir = Path(people_dir)
    return [
        load_person(path, catalog_items)
        for path in sorted(people_dir.glob("*.json"))
    ]


def active_people(people) -> list[dict]:
    return [p for p in people if p.get("active", True)]


def person_items(person, catalog_items) -> list[dict]:
    """그 사람이 고른 아이템의 카탈로그 항목을, person['items'] 순서대로 낸다."""
    by_id = {item["id"]: item for item in catalog_items}
    return [by_id[item_id] for item_id in person["items"]]
```

- [ ] **Step 5: 통과 확인**

Run: `python3 -m pytest tests/test_person.py -v`
Expected: PASS (8 passed)

- [ ] **Step 6: 커밋**

```bash
git add people/jammy.json src/routine-jammy/person.py tests/test_person.py
git commit -m "feat: add per-person routine config

A person is a chosen subset of catalog items plus a theme. Referencing an
item the catalog doesn't have is rejected at load time rather than silently
producing empty results mid-cron.

jammy selects all nine current items and keeps the pastel theme, so its
behavior is unchanged."
```

---

### Task 7: 사람별 데이터 경로

**Files:**
- Modify: `src/routine-jammy/weekly_refresh.py`
- Move: `docs/data/current-week.json` → `docs/data/jammy/current-week.json`
- Move: `docs/data/exercise-stats.json`, `docs/data/nutrition-stats.json` (있으면) → `docs/data/jammy/`
- Modify: `docs/app.js` (데이터 경로)
- Modify: `tests/test_weekly_refresh.py`, `tests/test_data_schema.py`

**Interfaces:**
- Produces:
  - `weekly_refresh.person_data_dir(repo_root, person_id) -> Path` → `docs/data/<person_id>`
  - `weekly_refresh.person_history_dir(repo_root, person_id) -> Path` → `history/<person_id>`

- [ ] **Step 1: 현재 데이터 파일 확인**

Run: `ls -la docs/data/ && ls -la history/`
Expected: `docs/data/`에 `current-week.json`, `routine-static.json`이 있고 `history/`는 비어 있다. `exercise-stats.json`/`nutrition-stats.json`은 주간 리프레시가 아직 안 돌아 없을 수 있다 — 없으면 이동 대상에서 뺀다.

> `routine-static.json`은 사람별 데이터가 아니라 앱 전역 정적 데이터이므로 **옮기지 않는다.**

- [ ] **Step 2: 파일 이동 (git mv로 이력 보존)**

```bash
mkdir -p docs/data/jammy
git mv docs/data/current-week.json docs/data/jammy/current-week.json
```

`exercise-stats.json`·`nutrition-stats.json`이 존재하면 같은 방식으로 옮긴다. 존재하지 않으면 이 스텝은 위 한 줄로 끝난다.

- [ ] **Step 3: 경로 헬퍼 테스트 추가**

`tests/test_weekly_refresh.py` 끝에 붙인다:

```python
from pathlib import Path

from weekly_refresh import person_data_dir, person_history_dir


def test_person_data_dir_is_namespaced():
    assert person_data_dir(Path("/repo"), "jammy") == Path("/repo/docs/data/jammy")


def test_person_history_dir_is_namespaced():
    assert person_history_dir(Path("/repo"), "jammy") == Path("/repo/history/jammy")
```

- [ ] **Step 4: 실패 확인**

Run: `python3 -m pytest tests/test_weekly_refresh.py -v`
Expected: FAIL — `ImportError: cannot import name 'person_data_dir'`

- [ ] **Step 5: 헬퍼 구현 + `main()` 수정**

`weekly_refresh.py`에 추가한다:

```python
def person_data_dir(repo_root: Path, person_id: str) -> Path:
    return repo_root / "docs" / "data" / person_id


def person_history_dir(repo_root: Path, person_id: str) -> Path:
    return repo_root / "history" / person_id
```

`main()`을 jammy 경로를 쓰도록 고친다:

```python
def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = execute(
        current_week_path=person_data_dir(repo_root, "jammy") / "current-week.json",
        history_dir=person_history_dir(repo_root, "jammy"),
        repo_root=repo_root,
    )
    print(json.dumps(result, ensure_ascii=False))
```

`commit_and_push()`의 `git add` 목록도 새 경로로 바꾼다:

```python
        [
            "git", "add", "history",
            "docs/data",
        ],
```

> 개별 파일을 나열하던 것을 디렉터리 두 개로 바꾼다. 사람이 늘면 파일 목록이 계속 늘어나기 때문이다. `docs/data`에는 사람별 산출물만 있고 `routine-static.json`은 손대지 않으므로 과잉 스테이징 위험이 없다.

- [ ] **Step 6: `docs/app.js` 데이터 경로 수정**

`docs/app.js`에서 `data/current-week.json`을 fetch 하는 곳을 `data/jammy/current-week.json`으로 바꾼다. `exercise-stats.json`·`nutrition-stats.json`도 같은 방식으로 `data/jammy/` 아래를 가리키게 한다.

Run: `grep -n "data/" docs/app.js`
로 대상 줄을 먼저 확인한 뒤 고친다.

> 프론트가 URL의 person을 읽어 경로를 만드는 것은 4단계(별도 계획)다. 지금은 jammy로 고정해 화면을 살려두는 최소 수정이다.

- [ ] **Step 7: 전체 스위트 통과 확인**

Run: `python3 -m pytest tests/ -q`
Expected: `98 passed`. `tests/test_data_schema.py`가 `docs/data/current-week.json`을 직접 열고 있으면 새 경로로 고친다.

- [ ] **Step 8: 화면 확인**

Run: `cd docs && python3 -m http.server 8899`
브라우저에서 `http://localhost:8899` 를 열어 오늘 카드·주간 계획·리포트 탭이 이전과 같이 뜨는지 본다. 확인 후 `Ctrl+C`.
Expected: 콘솔에 404 없음, 화면이 마이그레이션 전과 동일.

- [ ] **Step 9: 커밋**

```bash
git add -A
git commit -m "refactor: namespace per-person data under docs/data/<personId>/

current-week.json and the stats files move to docs/data/jammy/, and
history/ gains the same per-person level. routine-static.json stays put -
it's app-wide, not per-person.

app.js is pointed at the jammy path for now; reading the person from the
URL comes with the routing work."
```

---

### Task 8: `weekly_refresh`를 사람 단위로

**Files:**
- Modify: `src/routine-jammy/weekly_refresh.py`
- Modify: `tests/test_weekly_refresh.py`

**Interfaces:**
- Consumes: `person.load_person`, `person.person_items`, `catalog.load_catalog`
- Produces:
  - `weekly_refresh.run(current_week_path, history_dir, person, catalog_items, fetch_week_fn=..., estimate_meal_nutrition_fn=...) -> dict`
  - 반환 dict에 `personId`, `recordedDays` 키 추가

- [ ] **Step 1: 테스트를 새 시그니처로 고치고 케이스 추가**

`tests/test_weekly_refresh.py`의 기존 `run(...)` 호출에 `person`과 `catalog_items`를 넘기도록 고친다. 파일 상단에 픽스처를 추가한다:

```python
CATALOG_ITEMS = [
    {"id": "슬로우 조깅", "label": "슬로우 조깅", "group": "exercise", "ruleType": "binaryCheck"},
    {"id": "바이올린", "label": "바이올린", "group": "other", "ruleType": "timedPractice",
     "suggestion": "바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안"},
    {"id": "아점", "label": "아점", "group": "meal", "ruleType": "logging"},
]

PERSON = {
    "personId": "jammy",
    "displayName": "재미",
    "themeId": "pastel",
    "active": True,
    "items": ["슬로우 조깅", "바이올린", "아점"],
}
```

그리고 새 테스트를 끝에 붙인다:

```python
def test_run_records_person_id_in_result(tmp_path):
    current_week_path = tmp_path / "current-week.json"
    current_week_path.write_text(
        json.dumps({
            "weekId": "2026-W31",
            "startDate": "2026-07-27",
            "endDate": "2026-08-02",
            "days": [],
        }),
        encoding="utf-8",
    )

    def fake_fetch(week_id, person=None):
        return {"responses": [], "reflection": {}}

    result = run(
        current_week_path,
        tmp_path / "history",
        PERSON,
        CATALOG_ITEMS,
        fetch_week_fn=fake_fetch,
        estimate_meal_nutrition_fn=lambda note: {
            "kcal": 0.0, "protein": 0.0, "fat": 0.0, "carb": 0.0, "unmatchedItems": [],
        },
    )
    assert result["personId"] == "jammy"


def test_run_uses_only_the_persons_items(tmp_path):
    """카탈로그에 있어도 그 사람이 고르지 않은 아이템은 완료율에 나오면 안 된다."""
    current_week_path = tmp_path / "current-week.json"
    current_week_path.write_text(
        json.dumps({
            "weekId": "2026-W31",
            "startDate": "2026-07-27",
            "endDate": "2026-08-02",
            "days": [],
        }),
        encoding="utf-8",
    )
    narrow_person = {**PERSON, "items": ["슬로우 조깅"]}

    def fake_fetch(week_id, person=None):
        return {"responses": [], "reflection": {}}

    result = run(
        current_week_path,
        tmp_path / "history",
        narrow_person,
        CATALOG_ITEMS,
        fetch_week_fn=fake_fetch,
        estimate_meal_nutrition_fn=lambda note: {
            "kcal": 0.0, "protein": 0.0, "fat": 0.0, "carb": 0.0, "unmatchedItems": [],
        },
    )
    assert set(result["rates"]) == {"슬로우 조깅"}
    assert "바이올린" not in result["rates"]
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_weekly_refresh.py -v`
Expected: FAIL — `TypeError: run() takes 2 positional arguments but 4 were given`

- [ ] **Step 3: `run()` 시그니처와 본문 수정**

```python
def run(
    current_week_path: Path,
    history_dir: Path,
    person: dict,
    catalog_items: list,
    fetch_week_fn=fetch_week,
    estimate_meal_nutrition_fn=estimate_meal_nutrition,
) -> dict:
    current_week = json.loads(current_week_path.read_text(encoding="utf-8"))
    week_id = current_week["weekId"]
    person_id = person["personId"]

    selected = person_items(person, catalog_items)
    exercise_ids = item_ids(items_by_group(selected, "exercise"))
    meal_ids = item_ids(items_by_group(selected, "meal"))

    sheet_data = fetch_week_fn(week_id, person=person_id)
    rates = completion_by_category(sheet_data["responses"], selected)
    recorded = recorded_days_by_item(sheet_data["responses"], selected)
    ...
```

`previous_rates`를 읽는 부분 옆에 `previous_recorded`도 읽고, 조정 판정을 합친다:

```python
    previous_entry = (
        history["weeks"][previous_week_ids[-1]] if previous_week_ids else None
    )
    previous_rates = previous_entry["completionByCategory"] if previous_entry else None
    previous_recorded = previous_entry.get("recordedDays") if previous_entry else None

    low_ids = find_low_categories(rates, previous_rates)
    low_ids += find_low_logging_items(recorded, previous_recorded)
    adjustments = suggest_adjustments(low_ids, selected)
```

`entry`에 `recordedDays`를 추가한다:

```python
    entry = {
        "completionByCategory": rates,
        "recordedDays": recorded,
        "adjustmentsApplied": adjustments,
        ...
    }
```

반환 dict에 `personId`를 추가한다:

```python
    return {
        "personId": person_id,
        "weekId": week_id,
        ...
    }
```

임포트를 보강한다:

```python
from catalog import item_ids, items_by_group, load_catalog
from person import load_person, person_items
from routine_rules import (
    completion_by_category,
    find_low_categories,
    find_low_logging_items,
    recorded_days_by_item,
    suggest_adjustments,
)
```

- [ ] **Step 4: `execute()`와 `main()` 수정**

```python
def execute(current_week_path: Path, history_dir: Path, repo_root: Path,
            person: dict, catalog_items: list) -> dict:
    try:
        result = run(current_week_path, history_dir, person, catalog_items)
        commit_and_push(repo_root)
    except Exception as error:
        notify(build_failure_message(error))
        raise
    notify(build_success_message(result))
    return result


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    catalog_items = load_catalog(repo_root / "catalog.json")
    person = load_person(repo_root / "people" / "jammy.json", catalog_items)
    person_id = person["personId"]
    result = execute(
        current_week_path=person_data_dir(repo_root, person_id) / "current-week.json",
        history_dir=person_history_dir(repo_root, person_id),
        repo_root=repo_root,
        person=person,
        catalog_items=catalog_items,
    )
    print(json.dumps(result, ensure_ascii=False))
```

> 여러 사람을 순회하는 것은 6단계(별도 계획)다. 지금은 jammy 한 명을 사람 설정으로부터 읽어 돌린다.

- [ ] **Step 5: 통과 확인**

Run: `python3 -m pytest tests/ -q`
Expected: `100 passed`

- [ ] **Step 6: 커밋**

```bash
git add src/routine-jammy/weekly_refresh.py tests/test_weekly_refresh.py
git commit -m "refactor: run the weekly refresh for a specific person

run() now takes a person config and the catalog, scoring only the items
that person selected, and records recordedDays alongside completion rates
so the logging rule has a previous week to compare against.

Still one person per invocation - looping over people comes later."
```

---

### Task 9: Apps Script `person` 컬럼

**Files:**
- Modify: `apps-script/Code.gs`

**Interfaces:**
- Produces: Responses 시트 컬럼 `person` 추가(맨 앞), Reflections 시트 컬럼 `person` 추가. GET은 `person` 쿼리 파라미터로 필터.

- [ ] **Step 1: `doPost` 수정 — 컬럼·중복키·기본값**

`getOrCreateSheet_` 헤더에 `person`을 **맨 앞**에 넣는다:

```javascript
    const sheet = getOrCreateSheet_(RESPONSES_SHEET_NAME, [
      'person', 'weekId', 'day', 'item', 'checked', 'minutes', 'sleepHours', 'energy', 'note', 'timestamp',
    ]);
```

`person` 값을 정한다 (누락 시 기본값 — 프론트가 아직 안 보내므로 필수):

```javascript
    const person = body.person || DEFAULT_PERSON_;
```

파일 상단 상수 정의부에 추가한다:

```javascript
// 프론트가 person을 보내기 전까지의 하위 호환 기본값. 4단계에서 프론트가 항상 보내게 되면
// 그때도 이 기본값은 남겨둔다 - 옛 북마크로 들어온 요청이 조용히 사라지는 것보다 낫다.
const DEFAULT_PERSON_ = 'jammy';
```

**중복 판정 키에 person을 넣는다** (이게 없으면 두 사람의 같은 요일·같은 아이템 체크인이 서로를 덮어쓴다):

```javascript
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === person && data[i][1] === body.weekId
          && data[i][2] === body.day && data[i][3] === body.item) {
        rowIndex = i + 1;
        break;
      }
    }
```

행 배열 맨 앞에 `person`을 넣는다:

```javascript
    const row = [
      person, body.weekId, body.day, body.item, body.checked,
      body.minutes === undefined || body.minutes === null ? '' : body.minutes,
      body.sleepHours === undefined || body.sleepHours === null ? '' : body.sleepHours,
      body.energy === undefined || body.energy === null ? '' : body.energy,
      body.note === undefined || body.note === null ? '' : body.note,
      body.timestamp,
    ];
```

- [ ] **Step 2: 회고 시트도 동일하게 수정**

```javascript
      const reflectionSheet = getOrCreateSheet_(REFLECTIONS_SHEET_NAME, ['person', 'weekId', 'good', 'blocker', 'change']);
```

중복 판정을 `(person, weekId)`로:

```javascript
      for (let i = 1; i < reflectionData.length; i++) {
        if (reflectionData[i][0] === person && reflectionData[i][1] === body.weekId) {
          reflectionRow = i + 1;
          break;
        }
      }
```

값 배열 맨 앞에 `person`:

```javascript
      const reflectionValues = [
        person,
        body.weekId,
        body.reflection.good === undefined || body.reflection.good === null ? '' : body.reflection.good,
        body.reflection.blocker === undefined || body.reflection.blocker === null ? '' : body.reflection.blocker,
        body.reflection.change === undefined || body.reflection.change === null ? '' : body.reflection.change,
      ];
```

- [ ] **Step 3: `doGet` 전체 교체 — person 필터 + 컬럼 인덱스 이동**

`person`이 A열로 들어가면서 **모든 컬럼 인덱스가 1씩 밀린다.** 아래로 `doGet`을 통째로 바꾼다:

```javascript
function doGet(e) {
  if (!checkSecret_(e.parameter.secret)) {
    return jsonResponse_({ ok: false, error: 'invalid secret' });
  }
  const weekId = e.parameter.weekId;
  const person = e.parameter.person || DEFAULT_PERSON_;

  const sheet = getOrCreateSheet_(RESPONSES_SHEET_NAME, [
    'person', 'weekId', 'day', 'item', 'checked', 'minutes', 'sleepHours', 'energy', 'note', 'timestamp',
  ]);
  const data = sheet.getDataRange().getValues();
  const responses = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === person && data[i][1] === weekId) {
      responses.push({
        day: data[i][2],
        item: data[i][3],
        checked: data[i][4] === true || data[i][4] === 'TRUE',
        minutes: data[i][5],
        sleepHours: data[i][6],
        energy: data[i][7],
        note: data[i][8],
        timestamp: data[i][9],
      });
    }
  }

  const reflectionSheet = getOrCreateSheet_(REFLECTIONS_SHEET_NAME, ['person', 'weekId', 'good', 'blocker', 'change']);
  const reflectionData = reflectionSheet.getDataRange().getValues();
  let reflection = {};
  for (let i = 1; i < reflectionData.length; i++) {
    if (reflectionData[i][0] === person && reflectionData[i][1] === weekId) {
      reflection = { good: reflectionData[i][2], blocker: reflectionData[i][3], change: reflectionData[i][4] };
      break;
    }
  }

  return jsonResponse_({ person: person, weekId: weekId, responses: responses, reflection: reflection });
}
```

> 인덱스가 하나라도 어긋나면 `item`에 `checked` 값이 들어가는 식으로 **조용히 잘못된 데이터**가 흘러간다. Task 11 Step 7의 검증이 이걸 잡는 지점이다.

- [ ] **Step 4: 문법 검사**

Run: `node --check apps-script/Code.gs`
Expected: 출력 없음(문법 정상). `node`가 없으면 이 스텝은 건너뛰고 Apps Script 편집기에 붙여넣을 때 오류 표시로 확인한다.

- [ ] **Step 5: 커밋**

```bash
git add apps-script/Code.gs
git commit -m "feat: add person column to both sheets

The dedup key in doPost matched on (weekId, day, item) only, so once a
second person exists their check-in for the same day and item would
overwrite the first person's row. The key now leads with person, and the
reflections sheet gets the same treatment - it was keyed on weekId alone.

person defaults to jammy when absent so existing check-ins keep working
until the frontend starts sending it."
```

---

### Task 10: `sheet_client`에 person 전달

**Files:**
- Modify: `src/routine-jammy/sheet_client.py`
- Modify: `tests/test_sheet_client.py`

**Interfaces:**
- Produces: `sheet_client.fetch_week(week_id, person=None) -> dict`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_sheet_client.py` 끝에 붙인다:

```python
def test_fetch_week_sends_person_param(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"responses": []}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setenv("ROUTINE_APPS_SCRIPT_URL", "https://example.test/exec")
    monkeypatch.setenv("ROUTINE_SHARED_SECRET", "s3cret")
    monkeypatch.setattr("sheet_client.requests.get", fake_get)

    fetch_week("2026-W31", person="jammy")
    assert captured["params"]["person"] == "jammy"
    assert captured["params"]["weekId"] == "2026-W31"


def test_fetch_week_omits_person_when_not_given(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"responses": []}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setenv("ROUTINE_APPS_SCRIPT_URL", "https://example.test/exec")
    monkeypatch.setenv("ROUTINE_SHARED_SECRET", "s3cret")
    monkeypatch.setattr("sheet_client.requests.get", fake_get)

    fetch_week("2026-W31")
    assert "person" not in captured["params"]
```

- [ ] **Step 2: 실패 확인**

Run: `python3 -m pytest tests/test_sheet_client.py -v`
Expected: FAIL — `TypeError: fetch_week() got an unexpected keyword argument 'person'`

- [ ] **Step 3: 구현**

```python
def fetch_week(week_id: str, person: str | None = None) -> dict:
    """Apps Script 웹앱에서 해당 주차의 체크인 응답을 가져온다.

    person을 주면 그 사람의 행만 받는다. 생략하면 Apps Script의 기본 사람으로 처리된다.
    ROUTINE_APPS_SCRIPT_URL, ROUTINE_SHARED_SECRET 환경변수가 필요하다.
    """
    base_url = os.environ["ROUTINE_APPS_SCRIPT_URL"]
    secret = os.environ["ROUTINE_SHARED_SECRET"]
    params = {"secret": secret, "weekId": week_id}
    if person:
        params["person"] = person
    response = requests.get(base_url, params=params, timeout=15)
    if response.status_code != 200:
        raise SheetClientError(
            f"Apps Script GET failed with status {response.status_code}: {response.text}"
        )
    return response.json()
```

- [ ] **Step 4: 통과 확인**

Run: `python3 -m pytest tests/ -q`
Expected: `102 passed`

- [ ] **Step 5: 커밋**

```bash
git add src/routine-jammy/sheet_client.py tests/test_sheet_client.py
git commit -m "feat: pass person through to the sheet query"
```

---

### Task 11: 시트 마이그레이션 + 검증 게이트

기존 행에 `person`을 채운다. **이 Task를 통과하지 못하면 배포하지 않는다.**

**Files:**
- Create: `apps-script/migrate-person-column.gs`
- Modify: `specs/plans/operator-runbook.md`

- [ ] **Step 1: 마이그레이션 전 스냅샷 기록 (검증 기준선)**

배포된 앱을 열어 아래 값을 그대로 적어둔다. 이것이 마이그레이션 후 대조할 기준이다.

```
weekId:
카테고리별 완료율(7개 전부):
운동한 날 / 연속일수:
리포트 탭 - 이번 주 식사 기록 행 수:
리포트 탭 - 주간 평균 kcal/탄/지/단:
```

Run: `cd docs && python3 -m http.server 8899` 후 브라우저에서 확인, `Ctrl+C`.

- [ ] **Step 2: 마이그레이션 스크립트 작성**

```javascript
/**
 * 1회용 마이그레이션: person 컬럼이 없던 시절의 기존 행에 'jammy'를 채운다.
 *
 * 실행 방법: Apps Script 편집기에서 이 파일을 추가하고 migratePersonColumn 함수를
 * 한 번 실행한다. 두 번 실행해도 안전하다(이미 채워진 행은 건드리지 않는다).
 *
 * 실행 전 반드시 스프레드시트 사본을 만들어 둘 것.
 */
function migratePersonColumn() {
  const BACKFILL_PERSON = 'jammy';
  const spreadsheet = getSpreadsheet_();
  const report = [];

  [
    { name: RESPONSES_SHEET_NAME, oldHeader: ['weekId', 'day', 'item', 'checked', 'minutes', 'sleepHours', 'energy', 'note', 'timestamp'] },
    { name: REFLECTIONS_SHEET_NAME, oldHeader: ['weekId', 'good', 'blocker', 'change'] },
  ].forEach(function (target) {
    const sheet = spreadsheet.getSheetByName(target.name);
    if (!sheet) {
      report.push(target.name + ': 시트 없음, 건너뜀');
      return;
    }
    const values = sheet.getDataRange().getValues();
    if (values.length === 0) {
      report.push(target.name + ': 빈 시트, 건너뜀');
      return;
    }
    if (values[0][0] === 'person') {
      report.push(target.name + ': 이미 마이그레이션됨, 건너뜀');
      return;
    }

    sheet.insertColumnBefore(1);
    sheet.getRange(1, 1).setValue('person');
    const rowCount = values.length - 1;
    if (rowCount > 0) {
      const backfill = [];
      for (let i = 0; i < rowCount; i++) {
        backfill.push([BACKFILL_PERSON]);
      }
      sheet.getRange(2, 1, rowCount, 1).setValues(backfill);
    }
    report.push(target.name + ': ' + rowCount + '행에 person=' + BACKFILL_PERSON + ' 채움');
  });

  Logger.log(report.join('\n'));
  return report.join('\n');
}
```

- [ ] **Step 3: 스프레드시트 백업**

Google Sheets에서 `파일 > 사본 만들기`로 사본을 만든다. 이름에 날짜를 넣는다(예: `routine-jammy responses 백업 2026-07-31`).
Expected: 사본이 만들어졌고 원본과 행 수가 같다.

- [ ] **Step 4: 마이그레이션 실행**

Apps Script 편집기에서 `migrate-person-column.gs`를 추가하고 `migratePersonColumn`을 실행한다.
Expected: 실행 로그에 `Responses: N행에 person=jammy 채움`, `Reflections: M행에 person=jammy 채움`이 나온다. 앞서 확인한 대로 N은 60~130 범위일 것이다.

- [ ] **Step 5: 시트 육안 확인**

스프레드시트를 열어 확인한다:
- A열 헤더가 `person`이고 모든 데이터 행에 `jammy`가 채워져 있다
- B열이 `weekId`, C열이 `day`, D열이 `item`으로 한 칸씩 밀렸다
- 빈 person 셀이 없다

- [ ] **Step 6: 갱신된 `Code.gs` 배포**

Apps Script 편집기에서 Task 9의 `Code.gs`를 붙여넣고 `배포 > 배포 관리`에서 기존 배포의 새 버전을 만든다. **새 배포를 만들면 URL이 바뀌므로 반드시 기존 배포를 수정한다.**
Expected: 배포 URL이 `.env`의 `ROUTINE_APPS_SCRIPT_URL`과 동일하게 유지된다.

- [ ] **Step 7: 검증 게이트 — 마이그레이션 후 값 대조**

```bash
cd ~/dev-out/routine-jammy
set -a && source .env && set +a
python3 -c "
import sys; sys.path.insert(0, 'src/routine-jammy')
from sheet_client import fetch_week
data = fetch_week('2026-W31', person='jammy')
print('응답 행 수:', len(data['responses']))
print('회고:', data.get('reflection'))
"
```

Expected: 응답 행 수가 마이그레이션 전과 같고 0이 아니다. **0이 나오면 필터가 잘못된 것이니 즉시 중단하고 Step 6의 `doGet` 컬럼 인덱스를 다시 확인한다.**

- [ ] **Step 8: 검증 게이트 — 화면 대조**

Run: `cd docs && python3 -m http.server 8899` 후 브라우저에서 Step 1에 적어둔 값과 **전부** 대조한다.
Expected: 완료율 7개, 운동한 날/연속일수, 식사 기록 행 수, 주간 평균 영양소가 **모두 Step 1과 동일**. 하나라도 다르면 배포를 중단하고 원인을 찾는다.

- [ ] **Step 9: 체크인 왕복 확인**

배포된 앱(또는 로컬 서버)에서 오늘 항목 하나를 체크했다가 해제한다.
Expected: 스프레드시트에서 해당 행의 `person`이 `jammy`로 채워지고, 새 행이 중복 생성되지 않는다(기존 행이 갱신된다).

- [ ] **Step 10: 운영 런북에 절차 추가**

`specs/plans/operator-runbook.md`에 절을 추가한다:

```markdown
## 사람 추가하기

1. `catalog.json`에 그 사람에게 필요한 아이템이 없으면 먼저 추가한다.
2. `people/<personId>.json`을 만든다 (`people/jammy.json` 참고).
3. `docs/data/<personId>/current-week.json`을 만든다.
4. 커밋·푸시하면 GitHub Pages가 재배포된다.

Apps Script 배포와 스프레드시트는 건드리지 않는다 — `person` 컬럼으로 이미 나뉘어 있다.
```

- [ ] **Step 11: 커밋**

```bash
git add apps-script/migrate-person-column.gs specs/plans/operator-runbook.md
git commit -m "feat: backfill person column on existing sheet rows

One-time migration that inserts a person column at the front of both
sheets and fills existing rows with jammy. Idempotent - re-running skips
sheets that already have the column.

Verified against a pre-migration snapshot: completion rates, streak, meal
log and weekly nutrition averages all match."
```

---

## 완료 기준

- [ ] `python3 -m pytest tests/ -q` 가 102개 이상 통과
- [ ] `grep -rn "슬로우 조깅\|아점\|저녁" src/routine-jammy/` 가 아무것도 출력하지 않음
- [ ] jammy 화면의 완료율·연속일수·리포트 탭·주간 이력이 착수 전과 동일 (Task 11 Step 8에서 대조 완료)
- [ ] 시트 두 곳 모두 `person` 컬럼이 있고 빈 값이 없음
- [ ] 체크인 왕복이 정상 동작하고 중복 행이 생기지 않음

## 다음 계획으로 넘길 것

스펙 4~7단계: 프론트 라우팅(`?person=`), 히어로 테마 전환, 장식 슬롯 + 장식 스티커, 크론 people 루프화, 신규 사용자 온보딩 스킬. 이 계획이 끝난 뒤 별도로 작성한다.
