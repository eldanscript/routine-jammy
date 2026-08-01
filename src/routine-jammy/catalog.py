"""루틴 아이템 카탈로그 로드·검증·조회.

카탈로그는 '선택 가능한 루틴 아이템 종류'의 마스터 목록이다. 다른 모듈은 아이템 목록을
하드코딩하지 않고 반드시 여기를 통해 얻는다.
"""

import json
from pathlib import Path

RULE_TYPES = ("binaryCheck", "timedPractice", "logging", "adhocCheck")
GROUPS = ("exercise", "meal", "other", "medication")
_REQUIRED_FIELDS = ("id", "label", "group", "ruleType")


class CatalogError(ValueError):
    pass


def load_catalog(path: Path) -> list[dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("items")
    if not isinstance(items, list) or not items:
        raise CatalogError("catalog.json의 items가 비어 있거나 리스트가 아닙니다")

    seen = set()
    for item in items:
        for field in _REQUIRED_FIELDS:
            if not item.get(field):
                raise CatalogError(f"아이템에 필수 필드 {field}가 없습니다: {item}")
        if item["id"] in seen:
            raise CatalogError(f"중복된 아이템 id: {item['id']}")
        seen.add(item["id"])
        if item["group"] not in GROUPS:
            raise CatalogError(
                f"알 수 없는 group '{item['group']}' (허용: {', '.join(GROUPS)})"
            )
        if item["ruleType"] not in RULE_TYPES:
            raise CatalogError(
                f"알 수 없는 ruleType '{item['ruleType']}' (허용: {', '.join(RULE_TYPES)})"
            )
    return items


def item_ids(items) -> list[str]:
    return [item["id"] for item in items]


def items_by_group(items, group) -> list[dict]:
    return [item for item in items if item["group"] == group]


def items_by_rule_type(items, rule_type) -> list[dict]:
    return [item for item in items if item["ruleType"] == rule_type]
