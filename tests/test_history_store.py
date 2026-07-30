import json

from history_store import (
    extract_meal_log,
    load_history,
    render_week_markdown,
    save_week,
    save_week_markdown,
)

MEAL_IDS = ["아점", "저녁"]


def test_load_history_returns_empty_shape_when_missing(tmp_path):
    assert load_history(tmp_path) == {"weeks": {}}


def test_save_week_persists_and_round_trips(tmp_path):
    entry = {"completionByCategory": {"슬로우 조깅": 0.86}, "adjustmentsApplied": [], "reflection": {}}
    save_week(tmp_path, "2026-W31", entry)

    reloaded = load_history(tmp_path)
    assert reloaded["weeks"]["2026-W31"] == entry


def test_save_week_creates_history_dir_when_missing(tmp_path):
    history_dir = tmp_path / "does-not-exist-yet"
    entry = {"completionByCategory": {"슬로우 조깅": 0.86}, "adjustmentsApplied": [], "reflection": {}}

    save_week(history_dir, "2026-W31", entry)

    reloaded = load_history(history_dir)
    assert reloaded["weeks"]["2026-W31"] == entry


def test_save_week_markdown_creates_history_dir_when_missing(tmp_path):
    history_dir = tmp_path / "does-not-exist-yet"
    entry = {"completionByCategory": {"슬로우 조깅": 0.86}, "adjustmentsApplied": [], "reflection": {}}

    path = save_week_markdown(history_dir, "2026-W31", entry, MEAL_IDS)

    assert path.read_text(encoding="utf-8").startswith("# 2026-W31")


def test_extract_meal_log_collects_checked_meal_notes_by_day():
    responses = [
        {"day": "월", "item": "아점", "checked": True, "note": "계란볶음밥"},
        {"day": "월", "item": "저녁", "checked": True, "note": "샐러드"},
        {"day": "화", "item": "아점", "checked": False, "note": "먹지 않음"},
        {"day": "화", "item": "저녁", "checked": True, "note": ""},
        {"day": "수", "item": "스쿼트", "checked": True},
    ]
    assert extract_meal_log(responses, MEAL_IDS) == {
        "월": {"아점": "계란볶음밥", "저녁": "샐러드"},
    }


def test_save_week_markdown_includes_completion_and_reflection(tmp_path):
    entry = {
        "completionByCategory": {"슬로우 조깅": 0.86},
        "adjustmentsApplied": ["물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안"],
        "reflection": {"good": "조깅", "blocker": "야근", "change": "물 목표 낮추기"},
    }
    path = save_week_markdown(tmp_path, "2026-W31", entry, MEAL_IDS)
    text = path.read_text(encoding="utf-8")
    assert "슬로우 조깅: 86%" in text
    assert "물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안" in text
    assert "야근" in text


def test_render_week_markdown_includes_meal_log_and_exercise_summary():
    entry = {
        "completionByCategory": {"슬로우 조깅": 0.86},
        "adjustmentsApplied": [],
        "reflection": {},
        "meals": {
            "월": {"아점": "계란볶음밥", "저녁": "샐러드"},
            "화": {"아점": "김밥"},
        },
        "exerciseDaysThisWeek": 5,
        "exerciseStreak": 3,
    }
    text = render_week_markdown("2026-W31", entry, MEAL_IDS)

    assert "## 식사 기록" in text
    assert "월 - 아점: 계란볶음밥, 저녁: 샐러드" in text
    assert "화 - 아점: 김밥" in text
    assert "수" not in text.split("## 식사 기록")[1].split("##")[0]

    assert "## 운동 요약" in text
    assert "운동한 날: 5/7일" in text
    assert "연속 3일째" in text


def test_render_week_markdown_includes_nutrition_summary_and_recommendations():
    entry = {
        "completionByCategory": {"슬로우 조깅": 0.86},
        "adjustmentsApplied": [],
        "reflection": {},
        "nutrition": {
            "weeklyAverage": {"kcal": 1850.3, "protein": 95.4, "fat": 65.1, "carb": 210.2},
            "recommendations": ["단백질 비중이 낮은 편이에요 — 단백질 식품표를 참고해서 늘려보세요"],
            "unmatchedFoodItems": ["희귀채소"],
        },
    }
    text = render_week_markdown("2026-W31", entry, MEAL_IDS)

    assert "## 영양 요약 (주간 평균)" in text
    assert "1850kcal" in text
    assert "탄수화물 210g" in text
    assert "지방 65g" in text
    assert "단백질 95g" in text
    assert "단백질 비중이 낮은 편이에요 — 단백질 식품표를 참고해서 늘려보세요" in text
    assert "매칭 실패한 재료: 희귀채소" in text
    assert "⚠️" in text
    assert "식약처 공공 데이터베이스" in text


def test_render_week_markdown_omits_optional_sections_when_absent():
    entry = {
        "completionByCategory": {"슬로우 조깅": 0.86},
        "adjustmentsApplied": [],
        "reflection": {},
    }
    text = render_week_markdown("2026-W31", entry, MEAL_IDS)

    assert "## 식사 기록" not in text
    assert "## 운동 요약" not in text
    assert "## 영양 요약" not in text
