"""사람별 루틴 설정 로드·검증.

한 사람의 루틴은 '카탈로그에서 고른 아이템 목록 + 테마'다. 카탈로그에 없는 아이템을
참조하면 로드 단계에서 거부한다 — 크론이 돌다가 조용히 빈 결과를 내는 것보다 낫다.
"""

import json
from pathlib import Path

from catalog import item_ids

_REQUIRED_FIELDS = ("personId", "displayName", "themeId", "items")


class PersonError(ValueError):
    pass


def load_person(path: Path, catalog_items) -> dict:
    path = Path(path)
    config = json.loads(path.read_text(encoding="utf-8"))

    for field in _REQUIRED_FIELDS:
        if not config.get(field):
            raise PersonError(f"{path.name}에 필수 필드 {field}가 없습니다")

    if config["personId"] != path.stem:
        raise PersonError(
            f"personId '{config['personId']}'가 파일명 '{path.stem}'과 다릅니다"
        )

    known = set(item_ids(catalog_items))
    unknown = [item_id for item_id in config["items"] if item_id not in known]
    if unknown:
        raise PersonError(f"카탈로그에 없는 아이템: {', '.join(unknown)}")

    seen = set()
    duplicates = []
    for item_id in config["items"]:
        if item_id in seen and item_id not in duplicates:
            duplicates.append(item_id)
        seen.add(item_id)
    if duplicates:
        raise PersonError(f"중복된 아이템 id: {', '.join(duplicates)}")

    config.setdefault("active", True)
    return config


def load_all_people(people_dir: Path, catalog_items) -> list[dict]:
    people_dir = Path(people_dir)
    return [
        load_person(path, catalog_items)
        for path in sorted(people_dir.glob("*.json"))
    ]


def active_people(people) -> list[dict]:
    return [p for p in people if p.get("active", True)]


def person_items(person, catalog_items) -> list[dict]:
    """그 사람이 고른 아이템의 카탈로그 항목을, person['items'] 순서대로 낸다."""
    by_id = {item["id"]: item for item in catalog_items}
    return [by_id[item_id] for item_id in person["items"]]
