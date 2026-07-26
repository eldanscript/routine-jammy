import json

from history_store import load_history, save_week, save_week_markdown


def test_load_history_returns_empty_shape_when_missing(tmp_path):
    assert load_history(tmp_path) == {"weeks": {}}


def test_save_week_persists_and_round_trips(tmp_path):
    entry = {"completionByCategory": {"운동": 0.86}, "adjustmentsApplied": [], "reflection": {}}
    save_week(tmp_path, "2026-W31", entry)

    reloaded = load_history(tmp_path)
    assert reloaded["weeks"]["2026-W31"] == entry


def test_save_week_creates_history_dir_when_missing(tmp_path):
    history_dir = tmp_path / "does-not-exist-yet"
    entry = {"completionByCategory": {"운동": 0.86}, "adjustmentsApplied": [], "reflection": {}}

    save_week(history_dir, "2026-W31", entry)

    reloaded = load_history(history_dir)
    assert reloaded["weeks"]["2026-W31"] == entry


def test_save_week_markdown_creates_history_dir_when_missing(tmp_path):
    history_dir = tmp_path / "does-not-exist-yet"
    entry = {"completionByCategory": {"운동": 0.86}, "adjustmentsApplied": [], "reflection": {}}

    path = save_week_markdown(history_dir, "2026-W31", entry)

    assert path.read_text(encoding="utf-8").startswith("# 2026-W31")


def test_save_week_markdown_includes_completion_and_reflection(tmp_path):
    entry = {
        "completionByCategory": {"운동": 0.86},
        "adjustmentsApplied": ["물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안"],
        "reflection": {"good": "조깅", "blocker": "야근", "change": "물 목표 낮추기"},
    }
    path = save_week_markdown(tmp_path, "2026-W31", entry)
    text = path.read_text(encoding="utf-8")
    assert "운동: 86%" in text
    assert "물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안" in text
    assert "야근" in text
