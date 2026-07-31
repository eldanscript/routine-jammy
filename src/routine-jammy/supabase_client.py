"""Supabase(PostgREST) 저장소 클라이언트.

기존 sheet_client.fetch_week와 동일한 모양을 반환한다 — 그래야 파이프라인의 나머지
모듈(routine_rules, history_store, exercise_stats 등)을 건드리지 않는다.

읽기는 secret 키로 한다(RLS 우회). 이 모듈은 서버에서만 쓰이며 브라우저와 무관하다.
"""

import os

import requests

REFLECTION_ITEM = "회고"
_REFLECTION_KEYS = ("good", "blocker", "change")
_TIMEOUT = 15


class SupabaseClientError(RuntimeError):
    pass


def _shape_week(rows) -> dict:
    """PostgREST 행 목록을 파이프라인이 쓰는 모양으로 바꾼다.

    rows는 created_at 오름차순으로 들어온다고 가정한다(정렬은 Postgres가 한다).
    같은 (day, item)이 여러 번 나오면 뒤에 온 것이 최신이므로 덮어쓴다.
    회고는 주당 하나이므로 요일과 무관하게 마지막 것만 남긴다.
    """
    latest = {}
    reflection_row = None

    for row in rows:
        if row["item"] == REFLECTION_ITEM:
            reflection_row = row          # 오름차순이므로 마지막이 최신
            continue
        latest[(row["day"], row["item"])] = row

    responses = []
    for row in latest.values():
        payload = row.get("payload") or {}
        # payload를 먼저 펼치고 코어 필드를 나중에 씌운다 —
        # 조작된 payload가 checked/item/day를 덮어쓸 수 없게 하는 순서다.
        responses.append({
            **payload,
            "day": row["day"],
            "item": row["item"],
            "checked": row["checked"],
        })

    reflection = {}
    if reflection_row is not None:
        payload = reflection_row.get("payload") or {}
        reflection = {key: payload.get(key, "") for key in _REFLECTION_KEYS}

    return {"responses": responses, "reflection": reflection}


def fetch_week(week_id: str, person: str | None = None) -> dict:
    """해당 주차의 체크인을 가져와 파이프라인 모양으로 돌려준다.

    SUPABASE_URL, SUPABASE_SECRET_KEY 환경변수가 필요하다.
    """
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SECRET_KEY"]

    params = {
        "select": "*",
        "week_id": f"eq.{week_id}",
        # created_at 동률일 때를 위해 id를 2차 정렬키로 둔다.
        # 정렬을 Postgres에 맡기면 클라이언트가 타임스탬프를 파싱할 필요가 없다.
        "order": "created_at.asc,id.asc",
    }
    if person:
        params["person_id"] = f"eq.{person}"

    headers = {"apikey": secret, "Authorization": f"Bearer {secret}"}

    response = requests.get(
        f"{base_url}/rest/v1/checkins", params=params, headers=headers, timeout=_TIMEOUT
    )
    if response.status_code != 200:
        raise SupabaseClientError(
            f"Supabase GET failed with status {response.status_code}: {response.text}"
        )
    return _shape_week(response.json())
