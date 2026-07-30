import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TASKS = ["슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크", "간식섭취", "바이올린"]


def _load(name):
    return json.loads((REPO_ROOT / "docs" / "data" / name).read_text(encoding="utf-8"))


def _load_jammy(name):
    return json.loads((REPO_ROOT / "docs" / "data" / "jammy" / name).read_text(encoding="utf-8"))


def test_current_week_has_seven_days_with_required_tasks():
    week = _load_jammy("current-week.json")
    assert len(week["days"]) == 7
    for day in week["days"]:
        assert day["tasks"] == REQUIRED_TASKS
        assert "date" in day and "exercise" in day and "meal" in day


def test_current_week_id_matches_year_week_format():
    week = _load_jammy("current-week.json")
    import re
    assert re.match(r"^\d{4}-W\d{2}$", week["weekId"])


def test_last_day_has_three_reflection_prompts():
    week = _load_jammy("current-week.json")
    last_day = week["days"][-1]
    assert last_day["day"] == "일"
    assert len(last_day["reflectionPrompts"]) == 3


def test_routine_static_has_expected_top_level_keys():
    static_data = _load("routine-static.json")
    assert set(["exercise", "meal", "violin", "water"]).issubset(static_data.keys())
    assert set(["A", "B", "C"]).issubset(static_data["exercise"]["strength"].keys())
