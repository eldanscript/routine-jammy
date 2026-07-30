import json

import pytest
from catalog import (
    CatalogError,
    item_ids,
    items_by_group,
    items_by_rule_type,
    load_catalog,
)


def write_catalog(tmp_path, items):
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps({"schemaVersion": 1, "items": items}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_load_returns_items(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
    ])
    items = load_catalog(path)
    assert item_ids(items) == ["스쿼트"]


def test_suggestion_is_optional(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
        {"id": "바이올린", "label": "바이올린", "group": "other",
         "ruleType": "timedPractice", "suggestion": "줄이기"},
    ])
    items = load_catalog(path)
    assert items[0].get("suggestion") is None
    assert items[1]["suggestion"] == "줄이기"


def test_rejects_duplicate_id(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
        {"id": "스쿼트", "label": "스쿼트2", "group": "exercise", "ruleType": "binaryCheck"},
    ])
    with pytest.raises(CatalogError, match="중복"):
        load_catalog(path)


def test_rejects_unknown_rule_type(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "magic"},
    ])
    with pytest.raises(CatalogError, match="ruleType"):
        load_catalog(path)


def test_rejects_unknown_group(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "sport", "ruleType": "binaryCheck"},
    ])
    with pytest.raises(CatalogError, match="group"):
        load_catalog(path)


def test_rejects_missing_required_field(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
    ])
    with pytest.raises(CatalogError, match="label"):
        load_catalog(path)


def test_filters_by_group_and_rule_type(tmp_path):
    path = write_catalog(tmp_path, [
        {"id": "스쿼트", "label": "스쿼트", "group": "exercise", "ruleType": "binaryCheck"},
        {"id": "아점", "label": "아점", "group": "meal", "ruleType": "logging"},
    ])
    items = load_catalog(path)
    assert item_ids(items_by_group(items, "exercise")) == ["스쿼트"]
    assert item_ids(items_by_rule_type(items, "logging")) == ["아점"]


def test_real_catalog_contains_jammys_nine_items():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    items = load_catalog(repo_root / "catalog.json")
    assert set(item_ids(items)) >= {
        "슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크",
        "간식섭취", "바이올린", "아점", "저녁",
    }
