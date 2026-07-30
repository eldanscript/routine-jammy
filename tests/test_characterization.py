"""jammy의 현재 동작을 고정한다. 다중 사용자 리팩터가 이 값들을 바꾸면 C-1 위반이다.

이 파일은 리팩터 도중 시그니처가 바뀌면 함께 수정하되, **기대값(assert 우변)은 절대
바꾸지 않는다**. 기대값이 바뀌어야 통과한다면 그것은 회귀다.
"""

from pathlib import Path

from catalog import item_ids, items_by_group, load_catalog
from exercise_stats import (
    build_day_level,
    category_skip_pattern,
    days_with_any_exercise,
    exercised_sequence,
    longest_current_streak,
    rolling_completion_average,
)
from history_store import extract_meal_log, render_week_markdown
from routine_rules import completion_by_category, find_low_categories, suggest_adjustments

CATALOG = load_catalog(Path(__file__).resolve().parents[1] / "catalog.json")
EXERCISE_IDS = item_ids(items_by_group(CATALOG, "exercise"))
MEAL_IDS = item_ids(items_by_group(CATALOG, "meal"))

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

# Two prior archived weeks feeding jammy's multi-week aggregation (streak,
# rolling average, skip pattern). Shaped like the real history["weeks"]
# structure written by history_store.save_week. Not given by any brief —
# hand-built to be realistic, then the expected values below were hand-computed
# from it (not read back from the functions under test).
JAMMY_HISTORY = {
    "weeks": {
        "2026-W01": {
            "byDay": {
                "월": {"슬로우 조깅": True, "스쿼트": False, "데드리프트": False, "런지": False, "플랭크": False},
                "화": {"슬로우 조깅": False, "스쿼트": False, "데드리프트": False, "런지": False, "플랭크": False},
            },
            "completionByCategory": {
                "슬로우 조깅": 0.14, "스쿼트": 0.0, "데드리프트": 0.0,
                "런지": 0.0, "플랭크": 0.0, "간식섭취": 0.29, "바이올린": 0.0,
            },
        },
        "2026-W02": {
            "byDay": {
                "월": {"슬로우 조깅": True, "스쿼트": True, "데드리프트": False, "런지": True, "플랭크": True},
                "화": {"슬로우 조깅": True, "스쿼트": False, "데드리프트": False, "런지": False, "플랭크": False},
                "수": {"슬로우 조깅": True, "스쿼트": False, "데드리프트": False, "런지": False, "플랭크": False},
            },
            "completionByCategory": {
                "슬로우 조깅": 0.43, "스쿼트": 0.14, "데드리프트": 0.0,
                "런지": 0.14, "플랭크": 0.14, "간식섭취": 0.43, "바이올린": 0.0,
            },
        },
    }
}
JAMMY_CURRENT_WEEK_ID = "2026-W03"


def test_completion_rates_cover_exactly_the_seven_tracked_items():
    rates = completion_by_category(JAMMY_WEEK_RESPONSES, CATALOG)
    assert set(rates) == {
        "슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크", "간식섭취", "바이올린",
    }


def test_completion_rates_exact_values():
    rates = completion_by_category(JAMMY_WEEK_RESPONSES, CATALOG)
    assert rates["슬로우 조깅"] == round(2 / 7, 2)
    assert rates["스쿼트"] == round(1 / 7, 2)
    assert rates["데드리프트"] == 0.0
    assert rates["바이올린"] == 0.0


def test_meal_items_are_not_in_completion_rates():
    rates = completion_by_category(JAMMY_WEEK_RESPONSES, CATALOG)
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
    assert suggest_adjustments(["바이올린"], CATALOG) == [
        "바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안"
    ]
    assert suggest_adjustments(["간식섭취"], CATALOG) == [
        "간식섭취 체크 기준을 더 쉽게 낮추는 걸 제안"
    ]
    assert suggest_adjustments(["슬로우 조깅", "스쿼트", "플랭크"], CATALOG) == []


def test_exercise_day_count_ignores_non_exercise_items():
    day_level = build_day_level(JAMMY_WEEK_RESPONSES)
    assert days_with_any_exercise(day_level, EXERCISE_IDS) == 2


def test_meal_log_extraction():
    meals = extract_meal_log(JAMMY_WEEK_RESPONSES, MEAL_IDS)
    assert meals == {
        "월": {"아점": "달걀 2 + 그릭요거트", "저녁": "닭가슴살 100g"},
        "화": {"아점": "두부 200g"},
    }


def test_exercised_sequence_across_jammy_history_and_current_week():
    current_day_level = build_day_level(JAMMY_WEEK_RESPONSES)
    sequence = exercised_sequence(JAMMY_HISTORY, JAMMY_CURRENT_WEEK_ID, current_day_level, EXERCISE_IDS)
    # W01(월,화) + W02(월,화,수) + current(월,화,수) — 수요일 조깅 미체크로 끝난다.
    assert sequence == [True, False, True, True, True, True, True, False]


def test_current_streak_is_zero_when_jammy_week_ends_on_a_miss():
    sequence = [True, False, True, True, True, True, True, False]
    assert longest_current_streak(sequence) == 0


def test_rolling_completion_average_for_slow_jog_over_jammy_history():
    current_rate = round(2 / 7, 2)  # 슬로우 조깅's current-week rate, pinned above
    average = rolling_completion_average(
        JAMMY_HISTORY, "슬로우 조깅", JAMMY_CURRENT_WEEK_ID, current_rate, num_weeks=4
    )
    assert average == (0.14 + 0.43 + 0.29) / 3


def test_category_skip_pattern_across_jammy_history():
    current_day_level = build_day_level(JAMMY_WEEK_RESPONSES)
    pattern = category_skip_pattern(JAMMY_HISTORY, JAMMY_CURRENT_WEEK_ID, current_day_level, EXERCISE_IDS)

    assert pattern["월"]["데드리프트"] == 3  # never done, in any of the 3 weeks
    assert pattern["월"]["슬로우 조깅"] == 0  # done every 월 across all 3 weeks
    assert pattern["화"]["스쿼트"] == 3
    assert pattern["화"]["데드리프트"] == 3
    assert pattern["수"]["슬로우 조깅"] == 1  # done in W02's 수, missed in current week's 수
    assert pattern["수"]["스쿼트"] == 2
    assert pattern["목"] == {
        "슬로우 조깅": 0, "스쿼트": 0, "데드리프트": 0, "런지": 0, "플랭크": 0,
    }  # no week ever recorded a 목
    assert set(pattern.keys()) == {"월", "화", "수", "목", "금", "토", "일"}


def test_render_week_markdown_full_report_for_jammy_week():
    # Realistic entry shape as produced by weekly_refresh.run(): completion
    # rates + meal log reuse the pinned values above; exerciseStreak reuses the
    # 0 pinned above; nutrition/reflection are hand-crafted plausible values.
    entry = {
        "completionByCategory": {
            "슬로우 조깅": 0.29,
            "스쿼트": 0.14,
            "데드리프트": 0.0,
            "런지": 0.14,
            "플랭크": 0.14,
            "간식섭취": 0.14,
            "바이올린": 0.0,
        },
        "adjustmentsApplied": ["바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안"],
        "reflection": {
            "good": "슬로우 조깅을 두 번 했다",
            "blocker": "야근으로 수요일을 놓쳤다",
            "change": "수요일 알람을 맞춰두기",
        },
        "meals": {
            "월": {"아점": "달걀 2 + 그릭요거트", "저녁": "닭가슴살 100g"},
            "화": {"아점": "두부 200g"},
        },
        "exerciseDaysThisWeek": 2,
        "exerciseStreak": 0,
        "nutrition": {
            "weeklyAverage": {"kcal": 1620.4, "carb": 180.6, "fat": 55.2, "protein": 98.7},
            "recommendations": ["단백질 비중이 낮은 편이에요 — 단백질 식품표를 참고해서 늘려보세요"],
            "unmatchedFoodItems": ["그릭요거트"],
        },
    }

    text = render_week_markdown(JAMMY_CURRENT_WEEK_ID, entry, MEAL_IDS)

    expected = (
        "# 2026-W03 주간 요약\n"
        "\n"
        "## 카테고리별 완료율\n"
        "- 슬로우 조깅: 29%\n"
        "- 스쿼트: 14%\n"
        "- 데드리프트: 0%\n"
        "- 런지: 14%\n"
        "- 플랭크: 14%\n"
        "- 간식섭취: 14%\n"
        "- 바이올린: 0%\n"
        "\n"
        "## 이번에 적용한 보완\n"
        "- 바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안\n"
        "\n"
        "## 운동 요약\n"
        "- 운동한 날: 2/7일\n"
        "- 연속 0일째\n"
        "\n"
        "## 식사 기록\n"
        "- 월 - 아점: 달걀 2 + 그릭요거트, 저녁: 닭가슴살 100g\n"
        "- 화 - 아점: 두부 200g\n"
        "\n"
        "## 영양 요약 (주간 평균)\n"
        "- 1620kcal (탄수화물 181g / 지방 55g / 단백질 99g)\n"
        "- 단백질 비중이 낮은 편이에요 — 단백질 식품표를 참고해서 늘려보세요\n"
        "- 매칭 실패한 재료: 그릭요거트\n"
        "- ⚠️ 영양 수치는 식약처 공공 데이터베이스 자동 매칭 기반의 대략적 추정치입니다 "
        "(재료명이 가공식품/메뉴로 잘못 매칭될 수 있음).\n"
        "\n"
        "## 회고\n"
        "- 가장 잘 된 것: 슬로우 조깅을 두 번 했다\n"
        "- 가장 큰 방해 요인: 야근으로 수요일을 놓쳤다\n"
        "- 다음 주에 바꿀 것: 수요일 알람을 맞춰두기\n"
    )
    assert text == expected
