from catalog import load_catalog
from routine_rules import (
    completion_by_category,
    find_low_categories,
    find_low_logging_items,
    recorded_days_by_item,
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
