import json

from weekly_refresh import run


def _seed_current_week(path):
    path.write_text(
        json.dumps({
            "weekId": "2026-W31",
            "startDate": "2026-07-27",
            "endDate": "2026-08-02",
            "days": [{"day": "월", "date": "2026-07-27", "tasks": ["운동", "물"]}],
        }),
        encoding="utf-8",
    )


def test_run_writes_history_and_advances_week(tmp_path):
    current_week_path = tmp_path / "current-week.json"
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    _seed_current_week(current_week_path)

    def fake_fetch(week_id):
        assert week_id == "2026-W31"
        return {
            "responses": [{"day": "월", "item": "운동", "checked": True}],
            "reflection": {"good": "조깅"},
        }

    result = run(current_week_path, history_dir, fetch_week_fn=fake_fetch)

    assert result["weekId"] == "2026-W31"
    assert result["nextWeekId"] == "2026-W32"

    history = json.loads((history_dir / "data.json").read_text(encoding="utf-8"))
    assert "2026-W31" in history["weeks"]

    next_week = json.loads(current_week_path.read_text(encoding="utf-8"))
    assert next_week["weekId"] == "2026-W32"
    assert next_week["days"][0]["date"] == "2026-08-03"
