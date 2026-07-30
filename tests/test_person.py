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
