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
