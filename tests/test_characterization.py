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
