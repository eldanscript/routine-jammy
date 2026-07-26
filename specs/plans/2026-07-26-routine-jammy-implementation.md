# routine-jammy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pastel weekly-routine PWA (`eldanscript/routine-jammy`) end to end — static app shell, Google Sheets sync backend, weekly automation, and the reusable Claude skill/cron that keeps it running every Sunday.

**Architecture:** A static app shell (`docs/index.html` + `docs/app.js` + `docs/style.css`) is built once and never regenerated. Only `docs/data/current-week.json` changes weekly. Check-ins POST to a Google Apps Script web app backed by a Google Sheet; a Python module (`src/routine-jammy/`) pulls that data back via GET, scores completion, writes `history/`, and advances `current-week.json`. A CronCreate job (Sunday 18:00 Asia/Seoul) and a reusable `.claude/skills/weekly-routine-refresh` skill both drive that Python entrypoint.

**Tech Stack:** Vanilla HTML/CSS/JS (no build tool), Python 3.12+ with `requests` and `pytest`, Google Apps Script, GitHub Pages, dev-agent-team CronCreate/PushNotification.

## Global Constraints

- No build tooling for the frontend — plain HTML/CSS/JS only, no framework, no bundler.
- No Service Worker — the app must always show the latest `current-week.json` when reopened.
- `docs/` is the GitHub Pages publish source only. Specs and plans live under `specs/`, never `docs/`.
- Use the provided design asset kit in `docs/assets/` as-is (icons, stickers, hero images, `tokens.css`, PWA icons/manifest). Do not add new images.
- Pastel palette variables come from `docs/assets/tokens.css` (`--routine-mint`, `--routine-peach`, `--routine-lavender`, `--routine-butter`, `--routine-blue`, etc.) — do not hardcode new hex colors.
- Minimum touch target 44px, card corner radius 18px (per `docs/assets/ASSET_GUIDE.md`).
- Never commit sensitive personal numbers (e.g. body weight) — those stay in the Google Sheet only.
- Python code targets 3.12+, tested with `pytest`. Every pure-logic module gets unit tests (TDD: failing test → minimal implementation → passing test).
- Every commit follows this repo's existing convention: a `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer (see `git log` in this repo for the exact style).
- CronCreate and PushNotification are orchestrator-only tools — no subagent in this roster has them, so the cron-registration task is executed directly by the orchestrator, not delegated.

---

### Task 1: Routine content data files

**Agent:** backend-developer

**Files:**
- Create: `requirements.txt`
- Create: `docs/data/routine-static.json`
- Create: `docs/data/current-week.json`
- Test: `tests/test_data_schema.py`
- Test: `tests/conftest.py`

**Interfaces:**
- Produces: `docs/data/routine-static.json` with top-level keys `exercise` (`slowJog`, `strength.A/B/C`, `conditionRule`), `meal` (`target`, `formula`, `proteinFoods`, `hungryTip`, `fiberTip`), `violin` (`targetMinutes`), `water` (`targetGlasses`).
- Produces: `docs/data/current-week.json` with top-level keys `weekId` (`"2026-W31"` format `YYYY-Wnn`), `startDate`, `endDate` (ISO dates), `days` (array of 7 objects, each with `day`, `date`, `exercise.{type,label,detail}`, `meal.{breakfast,dinner}`, `tasks` — an array that must equal `["운동","단백질","채소","간식계획","바이올린","물"]` for every day). The last day (`일`) additionally has `reflectionPrompts` (array of 3 strings).
- Later tasks (2, 3, 6) read both files directly; keep the key names above stable.

- [ ] **Step 1: Write `tests/conftest.py` so tests can import the Python package**

```python
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "routine-jammy"
sys.path.insert(0, str(SRC_DIR))
```

- [ ] **Step 2: Write the failing schema test**

```python
# tests/test_data_schema.py
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TASKS = ["운동", "단백질", "채소", "간식계획", "바이올린", "물"]


def _load(name):
    return json.loads((REPO_ROOT / "docs" / "data" / name).read_text(encoding="utf-8"))


def test_current_week_has_seven_days_with_required_tasks():
    week = _load("current-week.json")
    assert len(week["days"]) == 7
    for day in week["days"]:
        assert day["tasks"] == REQUIRED_TASKS
        assert "date" in day and "exercise" in day and "meal" in day


def test_current_week_id_matches_year_week_format():
    week = _load("current-week.json")
    import re
    assert re.match(r"^\d{4}-W\d{2}$", week["weekId"])


def test_last_day_has_three_reflection_prompts():
    week = _load("current-week.json")
    last_day = week["days"][-1]
    assert last_day["day"] == "일"
    assert len(last_day["reflectionPrompts"]) == 3


def test_routine_static_has_expected_top_level_keys():
    static_data = _load("routine-static.json")
    assert set(["exercise", "meal", "violin", "water"]).issubset(static_data.keys())
    assert set(["A", "B", "C"]).issubset(static_data["exercise"]["strength"].keys())
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_data_schema.py -v`
Expected: FAIL — `docs/data/current-week.json` / `routine-static.json` not found.

- [ ] **Step 4: Write `docs/data/routine-static.json`**

```json
{
  "exercise": {
    "slowJog": {
      "title": "슬로우 조깅",
      "intensity": "RPE 4-6/10: 2-3문장 대화가 가능한 정도",
      "steps": [
        "워밍업 5분: 편한 걷기 + 발목·고관절 돌리기",
        "본운동 15-20분: 대화 가능한 속도, 필요하면 3분 조깅/1분 걷기",
        "쿨다운 5분: 느린 걷기 + 종아리·허벅지 가볍게 풀기"
      ]
    },
    "strength": {
      "A": {
        "day": "화",
        "title": "근력 A",
        "items": [
          {"name": "스쿼트", "detail": "2세트 x 8-10회"},
          {"name": "리버스 런지", "detail": "2세트 x 좌우 6회"},
          {"name": "글루트 브릿지", "detail": "2세트 x 10-12회"},
          {"name": "플랭크", "detail": "2세트 x 15-25초"}
        ],
        "note": "마지막 2회가 남는 여유로 종료"
      },
      "B": {
        "day": "목",
        "title": "근력 B",
        "items": [
          {"name": "힙힌지 연습", "detail": "벽 터치 2세트 x 8회"},
          {"name": "가벼운 데드리프트", "detail": "2세트 x 8회"},
          {"name": "스쿼트", "detail": "2세트 x 8회"},
          {"name": "브릿지 + 플랭크", "detail": "각 2세트"}
        ],
        "note": "마지막 2회가 남는 여유로 종료"
      },
      "C": {
        "day": "토",
        "title": "근력 C · 10분 최소 버전",
        "items": [],
        "note": "스쿼트·런지·힙힌지·브릿지·플랭크를 1-2세트씩 가볍게 복습. 시간/컨디션이 부족하면 워밍업 2분 + 스쿼트 8회 + 브릿지 10회 + 플랭크 15초를 2라운드만 해도 완료로 기록."
      }
    },
    "conditionRule": "통증·어지럼·비정상적 숨참이 있으면 중단. 피곤한 날은 10분 버전으로 바꾸면 성공!"
  },
  "meal": {
    "target": "하루 단백질 55-60g, 점심과 저녁에 25-30g씩",
    "formula": "단백질 25-30g + 채소 2가지 + 통곡/감자 등 탄수화물 + 물",
    "proteinFoods": [
      {"food": "계란 2개", "protein": "12g"},
      {"food": "그릭요거트 170g", "protein": "18g"},
      {"food": "닭가슴살 100g", "protein": "23g"},
      {"food": "소고기 우둔살 100g", "protein": "21g"},
      {"food": "돼지고기 100g", "protein": "20g"},
      {"food": "연어 100g", "protein": "20g"},
      {"food": "고등어 100g", "protein": "20g"},
      {"food": "새우 100g", "protein": "20g"},
      {"food": "두부 한모 300g", "protein": "24g"}
    ],
    "hungryTip": "물 한 잔 먼저, 그래도 배고프면 달걀·그릭요거트·두부·토마토 중 1가지를 계획 간식으로.",
    "fiberTip": "매 끼니 채소 2가지. 콩·통곡·과일도 번갈아 넣기."
  },
  "violin": {"title": "바이올린 연습", "targetMinutes": 15},
  "water": {"title": "물 섭취", "targetGlasses": 6}
}
```

- [ ] **Step 5: Write `docs/data/current-week.json`**

```json
{
  "weekId": "2026-W31",
  "startDate": "2026-07-27",
  "endDate": "2026-08-02",
  "days": [
    {
      "day": "월", "date": "2026-07-27",
      "exercise": {"type": "slowJog", "label": "슬로우 조깅", "detail": "25분 · 아주 편하게"},
      "meal": {"breakfast": "달걀 2 + 그릭요거트 + 베리", "dinner": "닭가슴살 100g + 두부 조금 + 채소"},
      "tasks": ["운동", "단백질", "채소", "간식계획", "바이올린", "물"]
    },
    {
      "day": "화", "date": "2026-07-28",
      "exercise": {"type": "strengthA", "label": "근력 A", "detail": "스쿼트·리버스런지·글루트브릿지·플랭크"},
      "meal": {"breakfast": "두부 200g + 달걀 2 + 나물", "dinner": "우둔살 120g + 쌈채소 + 잡곡"},
      "tasks": ["운동", "단백질", "채소", "간식계획", "바이올린", "물"]
    },
    {
      "day": "수", "date": "2026-07-29",
      "exercise": {"type": "slowJog", "label": "슬로우 조깅", "detail": "25-30분 · 대화 가능한 속도"},
      "meal": {"breakfast": "그릭요거트 + 달걀 2 + 과일", "dinner": "연어 120g + 구운 채소 + 감자"},
      "tasks": ["운동", "단백질", "채소", "간식계획", "바이올린", "물"]
    },
    {
      "day": "목", "date": "2026-07-30",
      "exercise": {"type": "strengthB", "label": "근력 B", "detail": "힙힌지·가벼운데드리프트·스쿼트·브릿지+플랭크"},
      "meal": {"breakfast": "달걀 2 + 두부 150g + 채소", "dinner": "돼지고기 살코기 120g + 채소볶음"},
      "tasks": ["운동", "단백질", "채소", "간식계획", "바이올린", "물"]
    },
    {
      "day": "금", "date": "2026-07-31",
      "exercise": {"type": "recoveryJog", "label": "회복 조깅", "detail": "20-25분 · 필요하면 걷기 섞기"},
      "meal": {"breakfast": "그릭요거트 + 달걀 2 + 견과", "dinner": "고등어 120g + 나물 2가지 + 잡곡"},
      "tasks": ["운동", "단백질", "채소", "간식계획", "바이올린", "물"]
    },
    {
      "day": "토", "date": "2026-08-01",
      "exercise": {"type": "strengthC", "label": "근력 C", "detail": "가볍게 전 동작 복습"},
      "meal": {"breakfast": "새우 120g + 달걀 1 + 샐러드", "dinner": "닭가슴살/두부 볼 + 다양한 채소"},
      "tasks": ["운동", "단백질", "채소", "간식계획", "바이올린", "물"]
    },
    {
      "day": "일", "date": "2026-08-02",
      "exercise": {"type": "recoveryReflect", "label": "회복 + 회고", "detail": "산책 20분 · 스트레칭 · 결과 입력"},
      "meal": {"breakfast": "남은 단백질 재료로 균형 한 접시", "dinner": "외식은 단백질·채소 먼저, 양은 편안하게"},
      "tasks": ["운동", "단백질", "채소", "간식계획", "바이올린", "물"],
      "reflectionPrompts": ["가장 잘 된 한 가지", "가장 큰 방해 요인", "다음 주에 바꿀 한 가지"]
    }
  ]
}
```

- [ ] **Step 6: Write `requirements.txt`**

```text
requests>=2.32
pytest>=8.0
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd ~/dev-out/routine-jammy && pip install -r requirements.txt && python3 -m pytest tests/test_data_schema.py -v`
Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
cd ~/dev-out/routine-jammy
git add requirements.txt docs/data/ tests/test_data_schema.py tests/conftest.py
git commit -m "$(cat <<'EOF'
feat: add weekly routine content data (2026-W31) and schema tests

Adopts the structure from the user's PDF sample (jog Mon/Wed/Fri,
strength A/B/C Tue/Thu/Sat, recovery+reflection Sunday) and adds the
one gap the asset kit implied but the PDF didn't check: daily water
intake.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Pure logic layer — completion scoring, history store, next-week builder

**Agent:** backend-developer

**Files:**
- Create: `src/routine-jammy/routine_rules.py`
- Create: `src/routine-jammy/history_store.py`
- Create: `src/routine-jammy/next_week_builder.py`
- Test: `tests/test_routine_rules.py`
- Test: `tests/test_history_store.py`
- Test: `tests/test_next_week_builder.py`

**Interfaces:**
- Consumes: nothing (pure functions / filesystem only).
- Produces (used by Task 3):
  - `routine_rules.completion_by_category(responses: list[dict]) -> dict[str, float]`
  - `routine_rules.find_low_categories(current_rates: dict, previous_rates: dict | None, threshold: float = 0.5) -> list[str]`
  - `routine_rules.suggest_adjustments(low_categories: list[str]) -> list[str]`
  - `history_store.load_history(history_dir: Path) -> dict`
  - `history_store.save_week(history_dir: Path, week_id: str, entry: dict) -> None`
  - `history_store.save_week_markdown(history_dir: Path, week_id: str, entry: dict) -> Path`
  - `next_week_builder.iso_week_id(date: datetime.date) -> str`
  - `next_week_builder.shift_week(current_week: dict) -> dict`

- [ ] **Step 1: Write failing tests for `routine_rules`**

```python
# tests/test_routine_rules.py
from routine_rules import completion_by_category, find_low_categories, suggest_adjustments


def test_completion_by_category_counts_checked_days():
    responses = [
        {"day": "월", "item": "운동", "checked": True},
        {"day": "화", "item": "운동", "checked": True},
        {"day": "수", "item": "운동", "checked": False},
        {"day": "월", "item": "물", "checked": True},
    ]
    rates = completion_by_category(responses)
    assert rates["운동"] == round(2 / 7, 2)
    assert rates["물"] == round(1 / 7, 2)
    assert rates["바이올린"] == 0.0


def test_find_low_categories_requires_two_consecutive_weeks():
    current = {"물": 0.3, "운동": 0.9}
    previous = {"물": 0.4, "운동": 0.8}
    assert find_low_categories(current, previous) == ["물"]


def test_find_low_categories_ignores_first_week_with_no_history():
    current = {"물": 0.2}
    assert find_low_categories(current, None) == []


def test_suggest_adjustments_maps_known_categories_only():
    assert suggest_adjustments(["물", "운동"]) == ["물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_routine_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routine_rules'`

- [ ] **Step 3: Implement `routine_rules.py`**

```python
"""Pure functions for scoring a week's check-ins and deciding routine adjustments."""

CATEGORIES = ["운동", "단백질", "채소", "간식계획", "바이올린", "물"]

_SUGGESTIONS = {
    "물": "물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안",
    "바이올린": "바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안",
    "간식계획": "간식계획 체크 기준을 더 쉽게 낮추는 걸 제안",
}


def completion_by_category(responses):
    totals = {category: 0 for category in CATEGORIES}
    for response in responses:
        if response["item"] in totals and response["checked"]:
            totals[response["item"]] += 1
    return {category: round(count / 7, 2) for category, count in totals.items()}


def find_low_categories(current_rates, previous_rates, threshold=0.5):
    if not previous_rates:
        return []
    low = []
    for category, rate in current_rates.items():
        previous_rate = previous_rates.get(category)
        if rate < threshold and previous_rate is not None and previous_rate < threshold:
            low.append(category)
    return low


def suggest_adjustments(low_categories):
    return [_SUGGESTIONS[category] for category in low_categories if category in _SUGGESTIONS]
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_routine_rules.py -v`
Expected: 4 passed

- [ ] **Step 5: Write failing tests for `history_store`**

```python
# tests/test_history_store.py
import json

from history_store import load_history, save_week, save_week_markdown


def test_load_history_returns_empty_shape_when_missing(tmp_path):
    assert load_history(tmp_path) == {"weeks": {}}


def test_save_week_persists_and_round_trips(tmp_path):
    entry = {"completionByCategory": {"운동": 0.86}, "adjustmentsApplied": [], "reflection": {}}
    save_week(tmp_path, "2026-W31", entry)

    reloaded = load_history(tmp_path)
    assert reloaded["weeks"]["2026-W31"] == entry


def test_save_week_markdown_includes_completion_and_reflection(tmp_path):
    entry = {
        "completionByCategory": {"운동": 0.86},
        "adjustmentsApplied": ["물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안"],
        "reflection": {"good": "조깅", "blocker": "야근", "change": "물 목표 낮추기"},
    }
    path = save_week_markdown(tmp_path, "2026-W31", entry)
    text = path.read_text(encoding="utf-8")
    assert "운동: 86%" in text
    assert "물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안" in text
    assert "야근" in text
```

- [ ] **Step 6: Run to verify failure**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_history_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'history_store'`

- [ ] **Step 7: Implement `history_store.py`**

```python
"""Read/write the local JSON+Markdown history mirror in history/."""

import json
from pathlib import Path


def load_history(history_dir: Path) -> dict:
    data_path = history_dir / "data.json"
    if not data_path.exists():
        return {"weeks": {}}
    return json.loads(data_path.read_text(encoding="utf-8"))


def save_week(history_dir: Path, week_id: str, entry: dict) -> None:
    history = load_history(history_dir)
    history["weeks"][week_id] = entry
    data_path = history_dir / "data.json"
    data_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def render_week_markdown(week_id: str, entry: dict) -> str:
    lines = [f"# {week_id} 주간 요약", "", "## 카테고리별 완료율"]
    for category, rate in entry["completionByCategory"].items():
        lines.append(f"- {category}: {round(rate * 100)}%")
    if entry.get("adjustmentsApplied"):
        lines.append("")
        lines.append("## 이번에 적용한 보완")
        for adjustment in entry["adjustmentsApplied"]:
            lines.append(f"- {adjustment}")
    reflection = entry.get("reflection")
    if reflection:
        lines.append("")
        lines.append("## 회고")
        lines.append(f"- 가장 잘 된 것: {reflection.get('good', '(입력 없음)')}")
        lines.append(f"- 가장 큰 방해 요인: {reflection.get('blocker', '(입력 없음)')}")
        lines.append(f"- 다음 주에 바꿀 것: {reflection.get('change', '(입력 없음)')}")
    return "\n".join(lines) + "\n"


def save_week_markdown(history_dir: Path, week_id: str, entry: dict) -> Path:
    md_path = history_dir / f"{week_id}.md"
    md_path.write_text(render_week_markdown(week_id, entry), encoding="utf-8")
    return md_path
```

- [ ] **Step 8: Run to verify pass**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_history_store.py -v`
Expected: 3 passed

- [ ] **Step 9: Write failing tests for `next_week_builder`**

```python
# tests/test_next_week_builder.py
import datetime

from next_week_builder import iso_week_id, shift_week


def test_iso_week_id_formats_year_and_week():
    assert iso_week_id(datetime.date(2026, 8, 3)) == "2026-W32"


def test_shift_week_moves_dates_forward_by_seven_days():
    current = {
        "weekId": "2026-W31",
        "startDate": "2026-07-27",
        "endDate": "2026-08-02",
        "days": [{"day": "월", "date": "2026-07-27", "tasks": ["운동", "물"]}],
    }
    next_week = shift_week(current)
    assert next_week["weekId"] == "2026-W32"
    assert next_week["startDate"] == "2026-08-03"
    assert next_week["days"][0]["date"] == "2026-08-03"
    assert next_week["days"][0]["tasks"] == ["운동", "물"]
```

- [ ] **Step 10: Run to verify failure**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_next_week_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'next_week_builder'`

- [ ] **Step 11: Implement `next_week_builder.py`**

```python
"""Builds next week's current-week.json from this week's template."""

import datetime


def iso_week_id(date: datetime.date) -> str:
    year, week, _ = date.isocalendar()
    return f"{year}-W{week:02d}"


def shift_week(current_week: dict) -> dict:
    start = datetime.date.fromisoformat(current_week["startDate"]) + datetime.timedelta(days=7)
    end = datetime.date.fromisoformat(current_week["endDate"]) + datetime.timedelta(days=7)
    new_days = []
    for day in current_week["days"]:
        old_date = datetime.date.fromisoformat(day["date"])
        new_date = old_date + datetime.timedelta(days=7)
        new_days.append({**day, "date": new_date.isoformat()})
    return {
        "weekId": iso_week_id(start),
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "days": new_days,
    }
```

- [ ] **Step 12: Run to verify pass**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_next_week_builder.py -v`
Expected: 2 passed

- [ ] **Step 13: Commit**

```bash
cd ~/dev-out/routine-jammy
git add src/routine-jammy/routine_rules.py src/routine-jammy/history_store.py \
        src/routine-jammy/next_week_builder.py \
        tests/test_routine_rules.py tests/test_history_store.py tests/test_next_week_builder.py
git commit -m "$(cat <<'EOF'
feat: add completion scoring, history store, and next-week builder

Pure, fully-tested modules with no I/O side effects beyond the
explicit history_dir path — weekly_refresh.py (Task 3) composes them.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Sheet client and weekly refresh orchestrator

**Agent:** backend-developer

**Files:**
- Create: `src/routine-jammy/sheet_client.py`
- Create: `src/routine-jammy/weekly_refresh.py`
- Test: `tests/test_sheet_client.py`
- Test: `tests/test_weekly_refresh.py`

**Interfaces:**
- Consumes: `routine_rules.completion_by_category/find_low_categories/suggest_adjustments`, `history_store.load_history/save_week/save_week_markdown`, `next_week_builder.shift_week` (all from Task 2).
- Produces: `sheet_client.fetch_week(week_id: str) -> dict`, `sheet_client.SheetClientError`; `weekly_refresh.run(current_week_path: Path, history_dir: Path, fetch_week_fn=fetch_week) -> dict`; `weekly_refresh.commit_and_push(repo_root: Path) -> None`; `weekly_refresh.main() -> None` (used by Task 5's skill and Task 8's cron).

- [ ] **Step 1: Write failing tests for `sheet_client`**

```python
# tests/test_sheet_client.py
import json

import pytest

import sheet_client


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_fetch_week_returns_parsed_json(monkeypatch):
    monkeypatch.setenv("ROUTINE_APPS_SCRIPT_URL", "https://script.google.com/macros/s/fake/exec")
    monkeypatch.setenv("ROUTINE_SHARED_SECRET", "test-secret")
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(200, {"weekId": "2026-W31", "responses": []})

    monkeypatch.setattr(sheet_client.requests, "get", fake_get)

    result = sheet_client.fetch_week("2026-W31")

    assert result == {"weekId": "2026-W31", "responses": []}
    assert captured["params"] == {"secret": "test-secret", "weekId": "2026-W31"}


def test_fetch_week_raises_on_non_200(monkeypatch):
    monkeypatch.setenv("ROUTINE_APPS_SCRIPT_URL", "https://script.google.com/macros/s/fake/exec")
    monkeypatch.setenv("ROUTINE_SHARED_SECRET", "test-secret")
    monkeypatch.setattr(
        sheet_client.requests, "get", lambda *a, **k: _FakeResponse(500, {"error": "boom"})
    )

    with pytest.raises(sheet_client.SheetClientError):
        sheet_client.fetch_week("2026-W31")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_sheet_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sheet_client'`

- [ ] **Step 3: Implement `sheet_client.py`**

```python
"""Thin HTTP client for the Apps Script web app backing the Google Sheet."""

import os

import requests


class SheetClientError(RuntimeError):
    pass


def fetch_week(week_id: str) -> dict:
    """GET the given week's check-in responses from the Apps Script web app.

    Requires ROUTINE_APPS_SCRIPT_URL and ROUTINE_SHARED_SECRET env vars.
    """
    base_url = os.environ["ROUTINE_APPS_SCRIPT_URL"]
    secret = os.environ["ROUTINE_SHARED_SECRET"]
    response = requests.get(
        base_url, params={"secret": secret, "weekId": week_id}, timeout=15
    )
    if response.status_code != 200:
        raise SheetClientError(
            f"Apps Script GET failed with status {response.status_code}: {response.text}"
        )
    return response.json()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_sheet_client.py -v`
Expected: 2 passed

- [ ] **Step 5: Write failing test for `weekly_refresh`**

```python
# tests/test_weekly_refresh.py
import json

from weekly_refresh import run


def _seed_current_week(path):
    path.write_text(
        json.dumps({
            "weekId": "2026-W31",
            "startDate": "2026-07-27",
            "endDate": "2026-08-02",
            "days": [{"day": "월", "date": "2026-07-27", "tasks": ["운동", "물"]}],
        }),
        encoding="utf-8",
    )


def test_run_writes_history_and_advances_week(tmp_path):
    current_week_path = tmp_path / "current-week.json"
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    _seed_current_week(current_week_path)

    def fake_fetch(week_id):
        assert week_id == "2026-W31"
        return {
            "responses": [{"day": "월", "item": "운동", "checked": True}],
            "reflection": {"good": "조깅"},
        }

    result = run(current_week_path, history_dir, fetch_week_fn=fake_fetch)

    assert result["weekId"] == "2026-W31"
    assert result["nextWeekId"] == "2026-W32"

    history = json.loads((history_dir / "data.json").read_text(encoding="utf-8"))
    assert "2026-W31" in history["weeks"]

    next_week = json.loads(current_week_path.read_text(encoding="utf-8"))
    assert next_week["weekId"] == "2026-W32"
    assert next_week["days"][0]["date"] == "2026-08-03"
```

- [ ] **Step 6: Run to verify failure**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_weekly_refresh.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'weekly_refresh'`

- [ ] **Step 7: Implement `weekly_refresh.py`**

```python
"""Weekly automation entrypoint: pulls last week's data, updates history, and
writes next week's current-week.json. Invoked by the CronCreate job every
Sunday 18:00 Asia/Seoul (Task 8), and by the weekly-routine-refresh skill (Task 5)."""

import json
import subprocess
from pathlib import Path

from history_store import load_history, save_week, save_week_markdown
from next_week_builder import shift_week
from routine_rules import completion_by_category, find_low_categories, suggest_adjustments
from sheet_client import fetch_week


def run(current_week_path: Path, history_dir: Path, fetch_week_fn=fetch_week) -> dict:
    current_week = json.loads(current_week_path.read_text(encoding="utf-8"))
    week_id = current_week["weekId"]

    sheet_data = fetch_week_fn(week_id)
    rates = completion_by_category(sheet_data["responses"])

    history = load_history(history_dir)
    previous_week_ids = sorted(w for w in history["weeks"] if w < week_id)
    previous_rates = (
        history["weeks"][previous_week_ids[-1]]["completionByCategory"]
        if previous_week_ids
        else None
    )
    low_categories = find_low_categories(rates, previous_rates)
    adjustments = suggest_adjustments(low_categories)

    entry = {
        "completionByCategory": rates,
        "adjustmentsApplied": adjustments,
        "reflection": sheet_data.get("reflection", {}),
    }
    save_week(history_dir, week_id, entry)
    save_week_markdown(history_dir, week_id, entry)

    next_week = shift_week(current_week)
    if adjustments:
        next_week["appliedAdjustments"] = adjustments
    current_week_path.write_text(
        json.dumps(next_week, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return {
        "weekId": week_id,
        "rates": rates,
        "adjustments": adjustments,
        "nextWeekId": next_week["weekId"],
    }


def commit_and_push(repo_root: Path) -> None:
    subprocess.run(["git", "add", "history", "docs/data/current-week.json"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: weekly routine refresh\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"],
        cwd=repo_root, check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo_root, check=True)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = run(
        current_week_path=repo_root / "docs" / "data" / "current-week.json",
        history_dir=repo_root / "history",
    )
    commit_and_push(repo_root)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Run to verify pass**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/test_weekly_refresh.py -v`
Expected: 1 passed

- [ ] **Step 9: Run the full Python suite**

Run: `cd ~/dev-out/routine-jammy && python3 -m pytest tests/ -v`
Expected: all tests pass (schema + rules + history + next-week + sheet client + weekly refresh)

- [ ] **Step 10: Commit**

```bash
cd ~/dev-out/routine-jammy
git add src/routine-jammy/sheet_client.py src/routine-jammy/weekly_refresh.py \
        tests/test_sheet_client.py tests/test_weekly_refresh.py
git commit -m "$(cat <<'EOF'
feat: add sheet client and weekly refresh orchestrator

Composes Task 2's pure modules into the end-to-end weekly job: fetch
last week from Apps Script, score it, write history, advance
current-week.json, commit and push. run()/commit_and_push() are split
so the core logic is unit-testable without touching git or the
network.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Apps Script backend (Code.gs)

**Agent:** backend-developer

**Files:**
- Create: `apps-script/Code.gs`
- Create: `apps-script/README.md`
- Create: `scripts/smoke_test_apps_script.sh`

**Interfaces:**
- Produces: a Web App exposing `doPost(e)` (accepts the same JSON shape `sheet_client`/the frontend send: `{secret, weekId, day, item, checked, minutes, sleepHours, energy, timestamp, reflection?}`) and `doGet(e)` (accepts `?secret=&weekId=`, returns `{weekId, responses: [...], reflection: {...}}` — the exact shape `sheet_client.fetch_week` expects from Task 3).
- Consumed by: Task 3's `sheet_client.fetch_week` (GET) and Task 6's `app.js` (POST).

This file runs in the Google Apps Script runtime, not this repo's Python/Node tooling, so it has no automated test here. Verification is a manual checklist plus a curl-based smoke test script run once against the real deployment.

- [ ] **Step 1: Write `apps-script/Code.gs`**

```javascript
/**
 * routine-jammy Apps Script backend.
 * Deploy as a Web App (Execute as: Me, Who has access: Anyone with the link).
 * Before deploying, set two Script Properties (Project Settings > Script Properties):
 *   ROUTINE_SHARED_SECRET  - a random string, must match docs/config.js's sharedSecret
 *   ROUTINE_SHEET_ID       - the spreadsheet ID to write into
 */

const RESPONSES_SHEET_NAME = 'responses';
const REFLECTIONS_SHEET_NAME = 'reflections';

function getSpreadsheet_() {
  const sheetId = PropertiesService.getScriptProperties().getProperty('ROUTINE_SHEET_ID');
  return SpreadsheetApp.openById(sheetId);
}

function getOrCreateSheet_(name, headerRow) {
  const spreadsheet = getSpreadsheet_();
  let sheet = spreadsheet.getSheetByName(name);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(name);
    sheet.appendRow(headerRow);
  }
  return sheet;
}

function checkSecret_(secret) {
  const expected = PropertiesService.getScriptProperties().getProperty('ROUTINE_SHARED_SECRET');
  return secret === expected;
}

function jsonResponse_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  if (!checkSecret_(body.secret)) {
    return jsonResponse_({ ok: false, error: 'invalid secret' });
  }

  const sheet = getOrCreateSheet_(RESPONSES_SHEET_NAME, [
    'weekId', 'day', 'item', 'checked', 'minutes', 'sleepHours', 'energy', 'timestamp',
  ]);
  const data = sheet.getDataRange().getValues();
  let rowIndex = -1;
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === body.weekId && data[i][1] === body.day && data[i][2] === body.item) {
      rowIndex = i + 1;
      break;
    }
  }
  const row = [
    body.weekId, body.day, body.item, body.checked,
    body.minutes || '', body.sleepHours || '', body.energy || '', body.timestamp,
  ];
  if (rowIndex > 0) {
    sheet.getRange(rowIndex, 1, 1, row.length).setValues([row]);
  } else {
    sheet.appendRow(row);
  }

  if (body.reflection) {
    const reflectionSheet = getOrCreateSheet_(REFLECTIONS_SHEET_NAME, ['weekId', 'good', 'blocker', 'change']);
    const reflectionData = reflectionSheet.getDataRange().getValues();
    let reflectionRow = -1;
    for (let i = 1; i < reflectionData.length; i++) {
      if (reflectionData[i][0] === body.weekId) {
        reflectionRow = i + 1;
        break;
      }
    }
    const reflectionValues = [
      body.weekId, body.reflection.good || '', body.reflection.blocker || '', body.reflection.change || '',
    ];
    if (reflectionRow > 0) {
      reflectionSheet.getRange(reflectionRow, 1, 1, reflectionValues.length).setValues([reflectionValues]);
    } else {
      reflectionSheet.appendRow(reflectionValues);
    }
  }

  return jsonResponse_({ ok: true });
}

function doGet(e) {
  if (!checkSecret_(e.parameter.secret)) {
    return jsonResponse_({ ok: false, error: 'invalid secret' });
  }
  const weekId = e.parameter.weekId;

  const sheet = getOrCreateSheet_(RESPONSES_SHEET_NAME, [
    'weekId', 'day', 'item', 'checked', 'minutes', 'sleepHours', 'energy', 'timestamp',
  ]);
  const data = sheet.getDataRange().getValues();
  const responses = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === weekId) {
      responses.push({
        day: data[i][1],
        item: data[i][2],
        checked: data[i][3] === true || data[i][3] === 'TRUE',
        minutes: data[i][4],
        sleepHours: data[i][5],
        energy: data[i][6],
        timestamp: data[i][7],
      });
    }
  }

  const reflectionSheet = getOrCreateSheet_(REFLECTIONS_SHEET_NAME, ['weekId', 'good', 'blocker', 'change']);
  const reflectionData = reflectionSheet.getDataRange().getValues();
  let reflection = {};
  for (let i = 1; i < reflectionData.length; i++) {
    if (reflectionData[i][0] === weekId) {
      reflection = { good: reflectionData[i][1], blocker: reflectionData[i][2], change: reflectionData[i][3] };
      break;
    }
  }

  return jsonResponse_({ weekId: weekId, responses: responses, reflection: reflection });
}
```

- [ ] **Step 2: Write `apps-script/README.md` with manual deploy steps**

```markdown
# Apps Script 배포 (최초 1회 수동)

1. https://script.google.com → 새 프로젝트
2. 기본 `Code.gs` 내용을 이 폴더의 `Code.gs`로 전부 교체
3. Google Sheets에서 새 스프레드시트를 만들고 URL의 `/d/<이 부분>/edit`에서 스프레드시트 ID 복사
4. 프로젝트 설정(톱니바퀴) → 스크립트 속성에 추가:
   - `ROUTINE_SHEET_ID` = 3에서 복사한 ID
   - `ROUTINE_SHARED_SECRET` = 임의의 긴 랜덤 문자열 (예: `openssl rand -hex 16`으로 생성)
5. 배포 → 새 배포 → 유형: 웹 앱
   - 실행 계정: 나
   - 액세스 권한: 링크가 있는 모든 사용자
6. 배포 후 나오는 웹 앱 URL을 복사해서:
   - `docs/config.js`의 `appsScriptUrl`에 붙여넣기
   - 같은 값을 `ROUTINE_APPS_SCRIPT_URL` 환경 변수로 저장(주간 자동화용)
   - `ROUTINE_SHARED_SECRET`은 `docs/config.js`의 `sharedSecret`과 4번의 스크립트 속성 두 곳에 동일하게 넣기
7. `scripts/smoke_test_apps_script.sh`로 배포 확인 (Step 3 참고)
```

- [ ] **Step 3: Write the smoke test script**

```bash
#!/usr/bin/env bash
# Usage: ROUTINE_APPS_SCRIPT_URL=... ROUTINE_SHARED_SECRET=... ./scripts/smoke_test_apps_script.sh
set -euo pipefail

: "${ROUTINE_APPS_SCRIPT_URL:?Set ROUTINE_APPS_SCRIPT_URL first}"
: "${ROUTINE_SHARED_SECRET:?Set ROUTINE_SHARED_SECRET first}"

echo "POST 체크인 테스트..."
curl -sS -X POST "$ROUTINE_APPS_SCRIPT_URL" \
  -H 'Content-Type: application/json' \
  -d "{\"secret\":\"$ROUTINE_SHARED_SECRET\",\"weekId\":\"2026-W00\",\"day\":\"월\",\"item\":\"운동\",\"checked\":true,\"timestamp\":\"2026-01-01T00:00:00+09:00\"}"
echo
echo "GET 조회 테스트..."
curl -sS "$ROUTINE_APPS_SCRIPT_URL?secret=$ROUTINE_SHARED_SECRET&weekId=2026-W00"
echo
```

- [ ] **Step 4: Make the script executable and commit**

```bash
cd ~/dev-out/routine-jammy
chmod +x scripts/smoke_test_apps_script.sh
git add apps-script/Code.gs apps-script/README.md scripts/smoke_test_apps_script.sh
git commit -m "$(cat <<'EOF'
feat: add Apps Script backend source and manual deploy guide

Code.gs can't be unit tested in this repo (Apps Script runtime), so
verification is the smoke test script run once against the real
deployment, per apps-script/README.md's manual steps.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Manual verification checklist (record result in the task, not automated)**

After the user deploys per `apps-script/README.md`:
```bash
ROUTINE_APPS_SCRIPT_URL="<deployed url>" ROUTINE_SHARED_SECRET="<secret>" ./scripts/smoke_test_apps_script.sh
```
Expected: POST prints `{"ok":true}`; GET prints a JSON object containing `"weekId":"2026-W00"` and a `responses` array with the one row just posted.

---

### Task 5: Reusable `weekly-routine-refresh` Claude skill

**Agent:** backend-developer

**Files:**
- Create: `.claude/skills/weekly-routine-refresh/SKILL.md`

**Interfaces:**
- Consumes: `weekly_refresh.main()` (Task 3), requires `ROUTINE_APPS_SCRIPT_URL`/`ROUTINE_SHARED_SECRET` env vars (Task 4's deployment).
- Produces: an invokable skill (`/weekly-routine-refresh`) that Task 8's CronCreate job calls, and that the user (or orchestrator) can also invoke manually any time.

- [ ] **Step 1: Write the skill file**

```markdown
---
name: weekly-routine-refresh
description: routine-jammy의 이번 주 결과를 리뷰하고 다음 주 루틴을 생성해 배포한다. 매주 일요일 18:00 KST 크론이 호출하거나, 필요할 때 수동으로 실행한다.
---

# Weekly Routine Refresh

`routine-jammy` 프로젝트(`~/dev-out/routine-jammy`)의 주간 자동화를 실행한다.

## 실행

```bash
cd ~/dev-out/routine-jammy
source .env 2>/dev/null || true   # ROUTINE_APPS_SCRIPT_URL / ROUTINE_SHARED_SECRET 로드
python3 src/routine-jammy/weekly_refresh.py
```

`weekly_refresh.main()`이 하는 일 (자세한 구현은 `src/routine-jammy/weekly_refresh.py`):
1. `docs/data/current-week.json`의 현재 주차를 읽는다.
2. Apps Script GET으로 그 주의 체크인 데이터를 가져온다.
3. 카테고리별 완료율을 계산하고, 2주 연속 50% 미만인 항목이 있으면 보수적인 조정을 제안한다.
4. `history/data.json`과 `history/<weekId>.md`에 이번 주 요약을 기록한다.
5. `docs/data/current-week.json`을 다음 주차로 갱신한다 (날짜만 +7일, 조정 사항이 있으면 `appliedAdjustments`로 표시).
6. 변경사항을 커밋하고 `origin/main`에 push한다 — GitHub Pages가 자동 재배포된다.

## 완료 후 알림

스크립트가 표준출력으로 찍는 JSON(`weekId`, `rates`, `adjustments`, `nextWeekId`)을 요약해서
PushNotification으로 사용자에게 전달한다. 예:

> 이번 주(2026-W31) 완료율 — 운동 86%, 물 57%. 물 섭취 목표를 낮추는 걸 제안했어요.
> 다음 주(2026-W32) 루틴이 배포됐습니다.

## 실패 시

Apps Script가 응답하지 않거나(`SheetClientError`) 배포가 아직 안 된 상태라면, 스크립트가
예외로 종료된다 — 이 경우 `docs/data/current-week.json`은 변경되지 않으므로 이전 주 루틴이
그대로 유지된다. 사용자에게 실패 사실과 원인을 알리고, `apps-script/README.md`의 배포 상태를
확인하도록 안내한다.
```

- [ ] **Step 2: Commit**

```bash
cd ~/dev-out/routine-jammy
git add .claude/skills/weekly-routine-refresh/SKILL.md
git commit -m "$(cat <<'EOF'
feat: add reusable weekly-routine-refresh skill

Wraps weekly_refresh.main() as an invokable skill so the same logic
serves both the Sunday 18:00 KST cron (Task 8) and any manual re-run.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Frontend PWA

**Agent:** frontend-developer

**Files:**
- Create: `docs/index.html`
- Create: `docs/style.css`
- Create: `docs/config.js`
- Create: `docs/js/routine-logic.js`
- Create: `docs/app.js`
- Test: `tests/js/routine-logic.test.js`

**Interfaces:**
- Consumes: `docs/data/routine-static.json`, `docs/data/current-week.json` (Task 1); `docs/assets/tokens.css`, `docs/assets/icons/*`, `docs/assets/images/stickers/*`, `docs/assets/images/hero/*`, `docs/manifest.webmanifest`, `docs/assets/pwa/*` (already committed in the initial scaffold commit).
- Produces: the deployed app itself — no other task consumes its internals, but its POST payload shape (`{weekId, day, item, checked, minutes, sleepHours, energy, timestamp, secret}`) must match Task 4's `Code.gs` `doPost` exactly.

- [ ] **Step 1: Write the failing Node test for the pure logic module**

```javascript
// tests/js/routine-logic.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const { completionRatio, isDayComplete } = require('../../docs/js/routine-logic.js');

test('completionRatio counts checked responses for one item over 7 days', () => {
  const responses = [
    { item: '운동', checked: true },
    { item: '운동', checked: true },
    { item: '운동', checked: false },
    { item: '물', checked: true },
  ];
  assert.equal(completionRatio(responses, '운동'), 2 / 7);
  assert.equal(completionRatio(responses, '물'), 1 / 7);
  assert.equal(completionRatio(responses, '바이올린'), 0);
});

test('isDayComplete is true only when every task for the day is checked', () => {
  assert.equal(isDayComplete(['운동', '물'], ['운동', '물']), true);
  assert.equal(isDayComplete(['운동', '물'], ['운동']), false);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/dev-out/routine-jammy && node --test tests/js/routine-logic.test.js`
Expected: FAIL — cannot find `docs/js/routine-logic.js`

- [ ] **Step 3: Implement `docs/js/routine-logic.js`**

```javascript
// Pure functions shared between the browser app and the Node test suite.
// No DOM access here — keep this file testable with `node --test`.

function completionRatio(responses, item) {
  const relevant = responses.filter((response) => response.item === item);
  const checkedCount = relevant.filter((response) => response.checked).length;
  return relevant.length === 0 ? 0 : checkedCount / 7;
}

function isDayComplete(dayTasks, checkedItems) {
  return dayTasks.every((task) => checkedItems.includes(task));
}

const RoutineLogic = { completionRatio, isDayComplete };

if (typeof module !== 'undefined' && module.exports) {
  module.exports = RoutineLogic;
} else {
  window.RoutineLogic = RoutineLogic;
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/dev-out/routine-jammy && node --test tests/js/routine-logic.test.js`
Expected: 2 passing

- [ ] **Step 5: Write `docs/config.js`**

```javascript
// Fill in after deploying apps-script/Code.gs as a Web App (see apps-script/README.md).
window.ROUTINE_CONFIG = {
  appsScriptUrl: '',
  sharedSecret: '',
};
```

- [ ] **Step 6: Write `docs/index.html`**

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>나를 돌보는 일주일 루틴</title>
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <meta name="apple-mobile-web-app-title" content="주간 루틴">
  <link rel="apple-touch-icon" href="assets/pwa/app-icon-192.png">
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="icon" href="assets/pwa/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="assets/tokens.css">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="app-header">
    <img src="assets/icons/logo-mark.svg" class="logo" alt="">
    <h1>나를 돌보는 일주일 루틴</h1>
  </header>

  <main id="view" class="view"></main>

  <nav class="bottom-nav" aria-label="주요 메뉴">
    <a href="#/" data-route="/"><img class="routine-icon" src="assets/icons/nav-home.svg" alt="">홈</a>
    <a href="#/week" data-route="/week"><img class="routine-icon" src="assets/icons/nav-calendar.svg" alt="">주간</a>
    <a href="#/check-in" data-route="/check-in" class="primary"><img class="routine-icon" src="assets/icons/nav-checkin.svg" alt="">체크</a>
    <a href="#/history" data-route="/history"><img class="routine-icon" src="assets/icons/nav-history.svg" alt="">리포트</a>
  </nav>

  <script src="config.js"></script>
  <script src="js/routine-logic.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 7: Write `docs/style.css`**

```css
body {
  margin: 0;
  font-family: var(--routine-font);
  background: var(--routine-bg);
  color: var(--routine-text);
  padding-bottom: 72px;
}

.app-header { display: flex; align-items: center; gap: 8px; padding: 16px; }
.app-header .logo { width: 32px; height: 32px; }
.app-header h1 { font-size: 18px; margin: 0; }

.view { padding: 0 16px 24px; max-width: 640px; margin: 0 auto; }

.today-card, .hero-card {
  background: var(--routine-surface);
  border-radius: var(--routine-radius-card);
  box-shadow: var(--routine-shadow-card);
  padding: 16px;
  margin-bottom: 16px;
}

.today-card.mint { background: var(--routine-mint); }
.today-card.peach { background: var(--routine-peach); }
.today-card.lavender { background: var(--routine-lavender); }
.today-card.butter { background: var(--routine-butter); }
.today-card.blue { background: var(--routine-blue); }
.today-card .sticker { width: 48px; height: 48px; }

.hero-card img { width: 100%; border-radius: var(--routine-radius-hero); display: block; }

.week-list { list-style: none; padding: 0; }
.week-card {
  display: flex;
  justify-content: space-between;
  background: var(--routine-surface);
  border-radius: var(--routine-radius-card);
  padding: 12px 16px;
  margin-bottom: 8px;
}

.meal-table { width: 100%; border-collapse: collapse; }
.meal-table th, .meal-table td {
  border-bottom: 1px solid var(--routine-border);
  padding: 8px;
  text-align: left;
  font-size: 14px;
}

.check-grid { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }
.check-item { display: flex; align-items: center; gap: 6px; min-height: 44px; min-width: 44px; }
.check-item input { width: 22px; height: 22px; }

.primary-button {
  min-height: 44px;
  border-radius: var(--routine-radius-control);
  border: none;
  background: var(--routine-mint-strong);
  color: white;
  padding: 0 20px;
  font-size: 15px;
}

.bottom-nav {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  display: flex;
  justify-content: space-around;
  background: var(--routine-surface);
  box-shadow: var(--routine-shadow-floating);
  padding: 8px 0 max(8px, env(safe-area-inset-bottom));
}

.bottom-nav a {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  text-decoration: none;
  color: var(--routine-text-muted);
  min-width: 44px;
  min-height: 44px;
}

.bottom-nav a.active { color: var(--routine-mint-strong); }

.muted { color: var(--routine-text-muted); font-size: 13px; }

@media print {
  .bottom-nav, .app-header { display: none; }
  body { background: white; padding-bottom: 0; }
}
```

- [ ] **Step 8: Write `docs/app.js`**

```javascript
(function () {
  const CONFIG = {
    appsScriptUrl: window.ROUTINE_CONFIG && window.ROUTINE_CONFIG.appsScriptUrl,
    sharedSecret: window.ROUTINE_CONFIG && window.ROUTINE_CONFIG.sharedSecret,
  };
  const QUEUE_KEY = 'routine-jammy:pending-checkins';
  const STICKER_BY_EXERCISE_TYPE = {
    slowJog: 'jogging', recoveryJog: 'jogging',
    strengthA: 'squat', strengthB: 'deadlift', strengthC: 'lunge',
    recoveryReflect: 'recovery',
  };

  let staticData = null;
  let weekData = null;

  async function loadData() {
    const [staticResponse, weekResponse] = await Promise.all([
      fetch('data/routine-static.json'),
      fetch('data/current-week.json'),
    ]);
    staticData = await staticResponse.json();
    weekData = await weekResponse.json();
  }

  function todayIndex() {
    const jsDay = new Date().getDay(); // 0=Sun..6=Sat
    return jsDay === 0 ? 6 : jsDay - 1; // map to 월=0..일=6
  }

  function getCheckedState() {
    const raw = localStorage.getItem(`routine-jammy:checked:${weekData.weekId}`);
    return raw ? JSON.parse(raw) : {};
  }

  function setChecked(day, item, checked) {
    const state = getCheckedState();
    state[day] = state[day] || {};
    state[day][item] = checked;
    localStorage.setItem(`routine-jammy:checked:${weekData.weekId}`, JSON.stringify(state));
  }

  function queueCheckin(payload) {
    const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    queue.push(payload);
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  }

  async function postCheckin(payload) {
    const response = await fetch(CONFIG.appsScriptUrl, {
      method: 'POST',
      body: JSON.stringify({ ...payload, secret: CONFIG.sharedSecret }),
    });
    if (!response.ok) throw new Error(`status ${response.status}`);
  }

  async function sendCheckin(payload) {
    if (!CONFIG.appsScriptUrl) {
      queueCheckin(payload);
      return;
    }
    try {
      await postCheckin(payload);
    } catch (error) {
      queueCheckin(payload);
    }
  }

  async function flushQueue() {
    if (!CONFIG.appsScriptUrl) return;
    const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    if (queue.length === 0) return;
    const remaining = [];
    for (const payload of queue) {
      try {
        await postCheckin(payload);
      } catch (error) {
        remaining.push(payload);
      }
    }
    localStorage.setItem(QUEUE_KEY, JSON.stringify(remaining));
  }

  function handleCheckboxChange(day, item) {
    return (event) => {
      const checked = event.target.checked;
      setChecked(day, item, checked);
      sendCheckin({ weekId: weekData.weekId, day, item, checked, timestamp: new Date().toISOString() });
    };
  }

  function renderHome() {
    const today = weekData.days[todayIndex()];
    const stickerName = STICKER_BY_EXERCISE_TYPE[today.exercise.type] || 'jogging';
    const adjustmentsCard = weekData.appliedAdjustments
      ? `<section class="today-card butter"><h2>이번 주 보완</h2><ul>${weekData.appliedAdjustments.map((a) => `<li>${a}</li>`).join('')}</ul></section>`
      : '';
    return `
      <section class="hero-card">
        <picture>
          <source media="(max-width: 640px)" srcset="assets/images/hero/dashboard-hero-mobile-800x1000.webp">
          <img src="assets/images/hero/dashboard-hero-768.webp" alt="운동, 건강한 식사, 바이올린과 체크 노트">
        </picture>
      </section>
      <section class="today-card mint">
        <img class="sticker" src="assets/images/stickers/${stickerName}.webp" alt="">
        <h2>오늘 (${today.day}) · ${today.exercise.label}</h2>
        <p>${today.exercise.detail}</p>
      </section>
      <section class="today-card peach">
        <img class="sticker" src="assets/images/stickers/meal.webp" alt="">
        <h2>오늘의 식단</h2>
        <p>아점: ${today.meal.breakfast}</p>
        <p>저녁: ${today.meal.dinner}</p>
      </section>
      <section class="today-card lavender">
        <img class="sticker" src="assets/images/stickers/violin.webp" alt="">
        <h2>바이올린 ${staticData.violin.targetMinutes}분</h2>
      </section>
      ${adjustmentsCard}
    `;
  }

  function renderWeek() {
    const cards = weekData.days.map((day) => `
      <li class="week-card"><strong>${day.day} ${day.date.slice(5)}</strong><span>${day.exercise.label} · ${day.exercise.detail}</span></li>
    `).join('');
    return `<h2>이번 주 한눈에</h2><ul class="week-list">${cards}</ul>`;
  }

  function renderExercise() {
    const strengthCards = ['A', 'B', 'C'].map((key) => {
      const block = staticData.exercise.strength[key];
      const items = (block.items || []).map((item) => `<li>${item.name} — ${item.detail}</li>`).join('');
      return `<div class="today-card lavender"><h3>${block.title}${block.day ? ' · ' + block.day : ''}</h3><ul>${items}</ul>${block.note ? `<p class="muted">${block.note}</p>` : ''}</div>`;
    }).join('');
    return `
      <h2>운동 루틴</h2>
      <p class="muted">${staticData.exercise.slowJog.intensity}</p>
      <div class="today-card mint">
        <h3>${staticData.exercise.slowJog.title}</h3>
        <ol>${staticData.exercise.slowJog.steps.map((step) => `<li>${step}</li>`).join('')}</ol>
      </div>
      ${strengthCards}
      <p class="muted">${staticData.exercise.conditionRule}</p>
    `;
  }

  function renderMeals() {
    const rows = weekData.days.map((day) => `<tr><td>${day.day}</td><td>${day.meal.breakfast}</td><td>${day.meal.dinner}</td></tr>`).join('');
    const foods = staticData.meal.proteinFoods.map((food) => `<li>${food.food} — ${food.protein}</li>`).join('');
    return `
      <h2>식단 루틴</h2>
      <p class="muted">${staticData.meal.target}</p>
      <div class="today-card peach"><strong>한 끼 공식</strong><p>${staticData.meal.formula}</p></div>
      <table class="meal-table"><thead><tr><th>요일</th><th>아점</th><th>저녁</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="today-card blue"><strong>단백질 식품표</strong><ul>${foods}</ul></div>
      <div class="today-card mint"><strong>배고플 때</strong><p>${staticData.meal.hungryTip}</p></div>
    `;
  }

  function renderCheckIn() {
    const checkedState = getCheckedState();
    const rows = weekData.days.map((day) => {
      const dayChecked = checkedState[day.day] || {};
      const checkboxes = day.tasks.map((task) => `
        <label class="check-item">
          <input type="checkbox" data-day="${day.day}" data-item="${task}" ${dayChecked[task] ? 'checked' : ''}>
          ${task}
        </label>
      `).join('');
      return `<div class="today-card"><strong>${day.day} ${day.date.slice(5)}</strong><div class="check-grid">${checkboxes}</div></div>`;
    }).join('');
    return `<h2>매일 체크</h2>${rows}`;
  }

  function renderHistory() {
    return `
      <h2>리포트</h2>
      <p class="muted">체크한 결과는 자동으로 동기화됩니다. 이번 주 결과를 문서로 남기고 싶으면 아래 버튼을 눌러주세요.</p>
      <button id="export-pdf" class="primary-button">이번 주 PDF로 내보내기</button>
    `;
  }

  function renderSettings() {
    return `
      <h2>설정</h2>
      <p class="muted">동기화 서버 연결: ${CONFIG.appsScriptUrl ? '연결됨' : '아직 설정되지 않음'}</p>
      <button id="clear-queue" class="primary-button">보내지 못한 체크 기록 초기화</button>
    `;
  }

  const ROUTES = {
    '/': renderHome, '/week': renderWeek, '/exercise': renderExercise, '/meals': renderMeals,
    '/check-in': renderCheckIn, '/history': renderHistory, '/settings': renderSettings,
  };

  function attachInteractions(route) {
    if (route === '/check-in') {
      document.querySelectorAll('#view input[type="checkbox"]').forEach((checkbox) => {
        checkbox.addEventListener('change', handleCheckboxChange(checkbox.dataset.day, checkbox.dataset.item));
      });
    }
    if (route === '/history') {
      const exportButton = document.getElementById('export-pdf');
      if (exportButton) exportButton.addEventListener('click', () => window.print());
    }
    if (route === '/settings') {
      const clearButton = document.getElementById('clear-queue');
      if (clearButton) clearButton.addEventListener('click', () => localStorage.removeItem(QUEUE_KEY));
    }
  }

  function render() {
    const route = location.hash.replace('#', '') || '/';
    const renderFn = ROUTES[route] || renderHome;
    document.getElementById('view').innerHTML = renderFn();
    document.querySelectorAll('.bottom-nav a').forEach((link) => {
      link.classList.toggle('active', link.dataset.route === route);
    });
    attachInteractions(route);
  }

  window.addEventListener('hashchange', render);
  window.addEventListener('online', flushQueue);

  loadData().then(() => {
    render();
    flushQueue();
  });
})();
```

- [ ] **Step 9: Manual smoke test in a local static server**

Run:
```bash
cd ~/dev-out/routine-jammy/docs && python3 -m http.server 8000
```
Open `http://localhost:8000` in a browser. Expected: 홈 화면에 오늘 카드가 뜨고, 하단 내비게이션의 4개 탭(홈/주간/체크/리포트)이 모두 콘텐츠를 렌더링하며, "오늘 체크" 탭에서 체크박스를 누르면 (Apps Script가 아직 없으므로) 콘솔 에러 없이 로컬 큐에 쌓인다 — `localStorage.getItem('routine-jammy:pending-checkins')`로 확인.

- [ ] **Step 10: Commit**

```bash
cd ~/dev-out/routine-jammy
git add docs/index.html docs/style.css docs/config.js docs/js/routine-logic.js docs/app.js tests/js/routine-logic.test.js
git commit -m "$(cat <<'EOF'
feat: build the routine-jammy frontend PWA

Hash-routed vanilla JS app over the seven navigation.json routes,
using the provided pastel asset kit as-is. No Service Worker by
design — the app must always show the latest current-week.json.
Offline check-ins queue in localStorage and flush on reconnect.
"PDF로 내보내기" uses window.print() with @media print rules rather
than a server-side renderer (YAGNI — no backend round trip needed).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: devops — GitHub Pages enablement and operator runbook

**Agent:** devops

**Files:**
- Create: `specs/plans/operator-runbook.md`

**Interfaces:**
- Consumes: `eldanscript/routine-jammy` repo (already pushed through Task 6), `docs/` as the Pages source.
- Produces: a live GitHub Pages URL that Task 8's cron pushes update; a runbook the orchestrator/user follow for one-time setup steps this agent cannot perform itself (Apps Script deploy needs an interactive Google login).

- [ ] **Step 1: Enable GitHub Pages from `main` / `docs`**

Run:
```bash
cd ~/dev-out/routine-jammy
gh api --method POST repos/eldanscript/routine-jammy/pages \
  -f "source[branch]=main" -f "source[path]=/docs" 2>&1 || \
gh api --method PUT repos/eldanscript/routine-jammy/pages \
  -f "source[branch]=main" -f "source[path]=/docs"
```
Expected: JSON response containing `"status"` and a `"html_url"` like `https://eldanscript.github.io/routine-jammy/`. (POST is used the first time; if Pages is already configured, POST 409s and the PUT branch updates it instead.)

- [ ] **Step 2: Verify the deployed page**

Run: `curl -sS -o /dev/null -w "%{http_code}\n" https://eldanscript.github.io/routine-jammy/`
Expected: `200` (may take 1-2 minutes after Step 1 for the first deploy to finish — retry with a short wait if it 404s once).

- [ ] **Step 3: Write the operator runbook**

```markdown
# routine-jammy 운영 런북

## 최초 설치 (1회, rainny가 직접 수행)
1. `apps-script/README.md`대로 Apps Script를 배포하고 `docs/config.js`에 URL/비밀키를 채운다
   (채운 뒤 `git add docs/config.js && git commit ... && git push`).
2. 대상 아이폰에서 Safari로 `https://eldanscript.github.io/routine-jammy/` 접속.
3. 공유 버튼 → "홈 화면에 추가".
4. `ROUTINE_APPS_SCRIPT_URL`/`ROUTINE_SHARED_SECRET`을 이 서버(dev-agent-team이 도는 머신)의
   환경 변수로도 저장한다 (주간 자동화 스크립트가 사용).

## 매주 확인
- 크론(Task 8)이 일요일 18:00 KST에 자동 실행되고 결과를 PushNotification으로 보낸다.
- 실패 알림이 오면 `apps-script/README.md`의 배포 상태와 Apps Script 실행 기록
  (script.google.com → 실행 기록)을 확인한다.

## GitHub Pages 상태 확인
```bash
gh api repos/eldanscript/routine-jammy/pages
```
`"status": "built"`이면 정상.
```

- [ ] **Step 4: Commit**

```bash
cd ~/dev-out/routine-jammy
git add specs/plans/operator-runbook.md
git commit -m "$(cat <<'EOF'
docs: add operator runbook and enable GitHub Pages

GitHub Pages now serves docs/ from main. Runbook covers the two
manual one-time steps no agent can do unattended (Apps Script Google
login, physically adding the home-screen icon on the target iPhone).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
git push origin main
```

---

### Task 8: Orchestrator — CronCreate weekly job and PushNotification wiring

**Agent:** 오케스트레이터 (직접 수행 — CronCreate/PushNotification은 서브에이전트 도구셋에 없음)

**Files:** none (harness-level scheduling configuration, not repo files).

- [ ] **Step 1: Confirm Task 3-7 are merged and reviewed (blocked by Task 9 passing, see below — do this step after Task 9 PASSes)**

- [ ] **Step 2: Register the CronCreate job**

Call `CronCreate` (load via `ToolSearch("select:CronCreate")` first) with: schedule = every Sunday 18:00 `Asia/Seoul`; action = invoke the `weekly-routine-refresh` skill (Task 5) in the `routine-jammy` project context; on completion, summarize the printed JSON (`weekId`, `rates`, `adjustments`, `nextWeekId`) and call `PushNotification` to the user with that summary.

- [ ] **Step 3: Send a test PushNotification to confirm delivery**

Call `PushNotification` with a short test message ("routine-jammy 주간 자동화가 등록되었습니다 — 다음 실행: 이번 주 일요일 18:00") and confirm with the user that it arrived on their device.

- [ ] **Step 4: Report the cron registration to the user**

State the cron ID/schedule and how to inspect or cancel it (`CronList`/`CronDelete`, loaded via `ToolSearch` when needed).

---

### Task 9: Reviewer gate

**Agent:** reviewer

**Files:** none (read-only review of the full diff since the initial scaffold commit).

- [ ] **Step 1: Run the reviewer agent over the branch**

Dispatch the `reviewer` agent against `eldanscript/routine-jammy`'s `main` branch (all commits from Task 1 through Task 7), specifically checking: the POST/GET payload shape matches between `docs/app.js`, `sheet_client.py`, and `Code.gs`; `docs/` contains no stray non-Pages files; no sensitive values (secrets, real personal health numbers) are committed; Python tests actually pass (`python3 -m pytest tests/ -v`) and Node tests pass (`node --test tests/js`).

- [ ] **Step 2: Address any CHANGES-REQUESTED findings**

Fix inline in the relevant task's files, re-run that task's tests, commit, and re-run Task 9 Step 1 until PASS.

- [ ] **Step 3: Only after PASS, proceed to Task 8 (CronCreate registration)**

Per this repo's CLAUDE.md: "reviewer가 PASS를 주기 전엔 merge하지 않는다" — here that means no cron goes live before reviewer PASS, since a live cron pushing to `main` unattended is the closest thing this project has to "merging" unreviewed automation into production.

---

## Self-Review Notes

- **Spec coverage:** §3(물 보완) → Task 1. §4(아키텍처, 앱 셸 고정) → Tasks 3,6. §5(7라우트) → Task 6. §6(API 계약) → Tasks 3,4,6 (payload shapes cross-checked in Task 9 Step 1). §7(에러 처리: 오프라인 큐, 첫 주, Apps Script 다운) → Task 6 Step 8 (`sendCheckin`/`flushQueue`), Task 3 (`run` leaves `current-week.json` untouched on fetch failure since it raises before any write), Task 5 (실패 시 안내). §8(프라이버시) → Global Constraints + CLAUDE.md 금지사항 already committed. §9(테스트 전략) → Tasks 1-3 pytest, Task 6 node --test. §"PDF 내보내기" (approved 2026-07-26) → Task 6 Step 8/10, resolves spec §10's open PDF-rendering question in favor of `window.print()` (no library needed).
- **Placeholder scan:** no TBD/TODO left; `docs/config.js`'s empty strings are a documented post-deploy fill-in, not an unresolved plan step.
- **Type consistency:** checked `weekly_refresh.run(current_week_path, history_dir, fetch_week_fn=fetch_week)` signature is identical between Task 3's implementation and Task 3's test. `history_store.save_week_markdown` return type (`Path`) matches its one caller in `weekly_refresh.py`. Frontend POST field names (`weekId, day, item, checked, minutes, sleepHours, energy, timestamp, secret`) match `Code.gs`'s `doPost` field reads exactly.
