from exercise_stats import (
    build_day_level,
    category_skip_pattern,
    days_with_any_exercise,
    exercised_sequence,
    longest_current_streak,
    rolling_completion_average,
    total_metric,
)

EXERCISE_IDS = ["슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크"]


def test_build_day_level_groups_items_by_day():
    responses = [
        {"day": "월", "item": "슬로우 조깅", "checked": True},
        {"day": "월", "item": "스쿼트", "checked": False},
        {"day": "화", "item": "런지", "checked": True},
    ]
    assert build_day_level(responses) == {
        "월": {"슬로우 조깅": True, "스쿼트": False},
        "화": {"런지": True},
    }


def test_days_with_any_exercise_ignores_non_exercise_categories():
    day_level = {
        "월": {"간식섭취": True, "바이올린": True},
        "화": {"스쿼트": True},
    }
    assert days_with_any_exercise(day_level, EXERCISE_IDS) == 1


def test_exercised_sequence_skips_weeks_without_byday():
    history = {
        "weeks": {
            "2026-W29": {"byDay": {"월": {"스쿼트": True}, "화": {"스쿼트": False}}},
            "2026-W30": {"completionByCategory": {"스쿼트": 0.5}},
        }
    }
    current_day_level = {"월": {"스쿼트": True}}

    assert exercised_sequence(history, "2026-W31", current_day_level, EXERCISE_IDS) == [True, False, True]


def test_longest_current_streak_counts_trailing_true_run():
    assert longest_current_streak([True, True, False, True, True, True]) == 3


def test_longest_current_streak_empty_sequence_is_zero():
    assert longest_current_streak([]) == 0


def test_longest_current_streak_trailing_false_is_zero():
    assert longest_current_streak([False]) == 0


def test_longest_current_streak_all_true_is_full_length():
    assert longest_current_streak([True, True, True]) == 3


def test_rolling_completion_average_includes_current_rate():
    history = {
        "weeks": {
            "2026-W28": {"completionByCategory": {"스쿼트": 0.5}},
            "2026-W29": {"completionByCategory": {"스쿼트": 0.7}},
            "2026-W30": {"completionByCategory": {"스쿼트": 0.9}},
        }
    }
    average = rolling_completion_average(history, "스쿼트", "2026-W31", 1.0, num_weeks=4)
    assert average == 0.775


def test_rolling_completion_average_skips_week_missing_category():
    history = {
        "weeks": {
            "2026-W29": {"completionByCategory": {"스쿼트": 0.5}},
            "2026-W30": {"completionByCategory": {"런지": 0.9}},
        }
    }
    average = rolling_completion_average(history, "스쿼트", "2026-W31", 1.0, num_weeks=4)
    assert average == (0.5 + 1.0) / 2


def test_rolling_completion_average_none_when_no_data():
    history = {"weeks": {}}
    assert rolling_completion_average(history, "스쿼트", "2026-W31", None, num_weeks=4) is None


def test_total_metric_sums_int_and_float_values():
    responses = [
        {"day": "월", "item": "슬로우 조깅", "checked": True, "km": 5},
        {"day": "화", "item": "슬로우 조깅", "checked": True, "km": 3.2},
    ]
    assert total_metric(responses, ["슬로우 조깅"], "km") == 8.2


def test_total_metric_ignores_null_value():
    responses = [{"day": "월", "item": "슬로우 조깅", "checked": True, "km": None}]
    assert total_metric(responses, ["슬로우 조깅"], "km") == 0.0


def test_total_metric_ignores_string_value():
    responses = [{"day": "월", "item": "슬로우 조깅", "checked": True, "km": "5.2"}]
    assert total_metric(responses, ["슬로우 조깅"], "km") == 0.0


def test_total_metric_ignores_bool_value():
    responses = [{"day": "월", "item": "슬로우 조깅", "checked": True, "km": True}]
    assert total_metric(responses, ["슬로우 조깅"], "km") == 0.0


def test_total_metric_ignores_unchecked_rows():
    responses = [{"day": "월", "item": "슬로우 조깅", "checked": False, "km": 5.0}]
    assert total_metric(responses, ["슬로우 조깅"], "km") == 0.0


def test_total_metric_ignores_missing_key():
    responses = [{"day": "월", "item": "슬로우 조깅", "checked": True}]
    assert total_metric(responses, ["슬로우 조깅"], "km") == 0.0


def test_total_metric_empty_responses_is_zero():
    assert total_metric([], ["슬로우 조깅"], "km") == 0.0


def test_category_skip_pattern_counts_missing_and_false_as_skips():
    history = {
        "weeks": {
            "2026-W29": {
                "byDay": {
                    "월": {"스쿼트": True},
                    "화": {"스쿼트": False},
                }
            },
        }
    }
    current_day_level = {
        "월": {"스쿼트": False},
    }

    pattern = category_skip_pattern(history, "2026-W30", current_day_level, EXERCISE_IDS)

    assert pattern["월"]["스쿼트"] == 1
    assert pattern["화"]["스쿼트"] == 1
    assert pattern["수"]["스쿼트"] == 0
    assert set(pattern.keys()) == {"월", "화", "수", "목", "금", "토", "일"}
    assert set(pattern["월"].keys()) == {"슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크"}
