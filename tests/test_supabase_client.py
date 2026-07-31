import pytest
from supabase_client import REFLECTION_ITEM, SupabaseClientError, _shape_week


def row(day, item, checked=True, payload=None, rid=1):
    return {
        "id": rid, "person_id": "jammy", "week_id": "2026-W31",
        "day": day, "item": item, "checked": checked,
        "payload": payload or {}, "created_at": "2026-08-01T00:00:00+00:00",
    }


def test_payload_is_flattened_to_top_level():
    rows = [row("월", "아점", payload={"note": "달걀 2"})]
    out = _shape_week(rows)
    assert out["responses"][0]["note"] == "달걀 2"
    assert out["responses"][0]["item"] == "아점"


def test_core_fields_win_over_payload():
    """조작된 payload가 checked 같은 코어 값을 덮어쓰면 안 된다."""
    rows = [row("월", "스쿼트", checked=True, payload={"checked": False, "item": "위조"})]
    out = _shape_week(rows)
    assert out["responses"][0]["checked"] is True
    assert out["responses"][0]["item"] == "스쿼트"


def test_later_row_wins_for_same_day_and_item():
    """행은 created_at 오름차순으로 들어온다고 가정한다 — 뒤에 온 것이 최신이다."""
    rows = [
        row("월", "스쿼트", checked=True, rid=1),
        row("월", "스쿼트", checked=False, rid=2),
    ]
    out = _shape_week(rows)
    assert len(out["responses"]) == 1
    assert out["responses"][0]["checked"] is False


def test_different_days_are_kept_separately():
    rows = [row("월", "스쿼트", rid=1), row("화", "스쿼트", rid=2)]
    out = _shape_week(rows)
    assert len(out["responses"]) == 2


def test_reflection_is_extracted_not_in_responses():
    rows = [
        row("월", "스쿼트"),
        row("일", REFLECTION_ITEM, payload={"good": "잘함", "blocker": "피곤", "change": "일찍자기"}),
    ]
    out = _shape_week(rows)
    assert [r["item"] for r in out["responses"]] == ["스쿼트"]
    assert out["reflection"] == {"good": "잘함", "blocker": "피곤", "change": "일찍자기"}


def test_reflection_dedupes_across_days_not_per_day():
    """회고는 주당 하나다. 다른 요일에 다시 써도 마지막 것만 남는다."""
    rows = [
        row("월", REFLECTION_ITEM, payload={"good": "첫번째", "blocker": "", "change": ""}, rid=1),
        row("수", REFLECTION_ITEM, payload={"good": "두번째", "blocker": "", "change": ""}, rid=2),
    ]
    out = _shape_week(rows)
    assert out["reflection"]["good"] == "두번째"
    assert out["responses"] == []


def test_missing_reflection_is_empty_dict():
    out = _shape_week([row("월", "스쿼트")])
    assert out["reflection"] == {}


def test_reflection_fills_missing_keys_with_empty_string():
    rows = [row("일", REFLECTION_ITEM, payload={"good": "있음"})]
    out = _shape_week(rows)
    assert out["reflection"] == {"good": "있음", "blocker": "", "change": ""}


def test_empty_rows_gives_empty_shape():
    assert _shape_week([]) == {"responses": [], "reflection": {}}


def test_null_payload_is_treated_as_empty():
    rows = [{**row("월", "스쿼트"), "payload": None}]
    out = _shape_week(rows)
    assert out["responses"][0]["checked"] is True


def test_fetch_week_requires_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    from supabase_client import fetch_week
    with pytest.raises(KeyError):
        fetch_week("2026-W31", person="jammy")


def test_fetch_week_sends_expected_query(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        def json(self):
            return []

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setattr("supabase_client.requests.get", fake_get)

    from supabase_client import fetch_week
    fetch_week("2026-W31", person="jammy")

    assert captured["url"] == "https://example.test/rest/v1/checkins"
    assert captured["params"]["person_id"] == "eq.jammy"
    assert captured["params"]["week_id"] == "eq.2026-W31"
    # 정렬은 Postgres에 맡긴다 — 클라이언트가 타임스탬프를 파싱하지 않는다
    assert captured["params"]["order"] == "created_at.asc,id.asc"
    assert captured["headers"]["apikey"] == "sb_secret_x"


def test_fetch_week_raises_on_non_200(monkeypatch):
    class FakeResponse:
        status_code = 500
        text = "boom"
        def json(self):
            return {}

    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setattr("supabase_client.requests.get",
                        lambda *a, **k: FakeResponse())

    from supabase_client import fetch_week
    with pytest.raises(SupabaseClientError, match="500"):
        fetch_week("2026-W31", person="jammy")
