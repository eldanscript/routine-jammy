import json
from pathlib import Path

from catalog import item_ids, items_by_rule_type, load_catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TASKS = [
    "슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크", "간식섭취", "바이올린",
    "고지혈증약", "코큐텐", "비타민C/D", "마그네슘",
]

_MEAL_ITEMS = {"아점", "저녁"}


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


def test_items_json_suggestions_match_catalog_adhoc_check_ids():
    items_data = _load_jammy("items.json")
    catalog = load_catalog(REPO_ROOT / "catalog.json")
    adhoc_ids = set(item_ids(items_by_rule_type(catalog, "adhocCheck")))
    assert set(items_data["suggestions"]["exercise"]) == adhoc_ids


def test_items_json_metric_keys_exist_in_catalog():
    items_data = _load_jammy("items.json")
    catalog = load_catalog(REPO_ROOT / "catalog.json")
    catalog_ids = set(item_ids(catalog))
    assert set(items_data["metrics"].keys()) <= catalog_ids


def test_items_json_groups_cover_current_week_tasks_and_match_catalog():
    items_data = _load_jammy("items.json")
    catalog = load_catalog(REPO_ROOT / "catalog.json")
    catalog_group_by_id = {item["id"]: item["group"] for item in catalog}
    section_ids = {section["id"] for section in items_data["sections"]}
    week = _load_jammy("current-week.json")

    for task in week["days"][0]["tasks"]:
        assert task in items_data["groups"], f"{task}가 items.json groups에 없습니다"

    for item_id, group in items_data["groups"].items():
        assert group == catalog_group_by_id[item_id]
        assert group in section_ids


def test_items_json_section_ids_are_unique():
    items_data = _load_jammy("items.json")
    section_ids = [section["id"] for section in items_data["sections"]]
    assert len(section_ids) == len(set(section_ids))
