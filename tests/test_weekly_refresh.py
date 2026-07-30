import json
import subprocess

import pytest

import weekly_refresh
from weekly_refresh import commit_and_push, execute, run
from telegram_notifier import NotifierError


def _seed_current_week(path):
    path.write_text(
        json.dumps({
            "weekId": "2026-W31",
            "startDate": "2026-07-27",
            "endDate": "2026-08-02",
            "days": [{"day": "월", "date": "2026-07-27", "tasks": ["슬로우 조깅", "물"]}],
        }),
        encoding="utf-8",
    )


def _fake_estimate_meal_nutrition(note):
    fixtures = {
        "계란후라이": {"kcal": 200.0, "protein": 14.0, "fat": 16.0, "carb": 1.0,
                    "matchedItems": [{"food_name": "계란후라이", "grams": 100.0}], "unmatchedItems": []},
        "샐러드": {"kcal": 100.0, "protein": 4.0, "fat": 2.0, "carb": 18.0,
                  "matchedItems": [{"food_name": "샐러드", "grams": 100.0}], "unmatchedItems": ["희귀채소"]},
    }
    return fixtures[note]


def test_run_writes_history_and_advances_week(tmp_path):
    current_week_path = tmp_path / "current-week.json"
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    _seed_current_week(current_week_path)

    def fake_fetch(week_id):
        assert week_id == "2026-W31"
        return {
            "responses": [
                {"day": "월", "item": "스쿼트", "checked": False},
                {"day": "월", "item": "아점", "checked": True, "note": "계란후라이"},
                {"day": "화", "item": "슬로우 조깅", "checked": True},
                {"day": "화", "item": "저녁", "checked": True, "note": "샐러드"},
                {"day": "수", "item": "스쿼트", "checked": True},
            ],
            "reflection": {"good": "조깅"},
        }

    result = run(
        current_week_path, history_dir,
        fetch_week_fn=fake_fetch,
        estimate_meal_nutrition_fn=_fake_estimate_meal_nutrition,
    )

    assert result["weekId"] == "2026-W31"
    assert result["nextWeekId"] == "2026-W32"
    assert result["exerciseDaysThisWeek"] == 2
    assert result["exerciseStreak"] == 2
    assert result["nutritionWeeklyAverage"] == {"kcal": 150.0, "protein": 9.0, "fat": 9.0, "carb": 9.5}

    history = json.loads((history_dir / "data.json").read_text(encoding="utf-8"))
    assert "2026-W31" in history["weeks"]
    entry = history["weeks"]["2026-W31"]
    assert entry["byDay"] == {
        "월": {"스쿼트": False, "아점": True},
        "화": {"슬로우 조깅": True, "저녁": True},
        "수": {"스쿼트": True},
    }
    assert entry["meals"] == {
        "월": {"아점": "계란후라이"},
        "화": {"저녁": "샐러드"},
    }
    assert entry["exerciseDaysThisWeek"] == 2
    assert entry["exerciseStreak"] == 2
    assert entry["nutrition"]["dailyTotals"] == {
        "월": {"kcal": 200.0, "protein": 14.0, "fat": 16.0, "carb": 1.0},
        "화": {"kcal": 100.0, "protein": 4.0, "fat": 2.0, "carb": 18.0},
    }
    assert entry["nutrition"]["weeklyAverage"] == {"kcal": 150.0, "protein": 9.0, "fat": 9.0, "carb": 9.5}
    assert entry["nutrition"]["unmatchedFoodItems"] == ["희귀채소"]
    assert isinstance(entry["nutrition"]["recommendations"], list)

    next_week = json.loads(current_week_path.read_text(encoding="utf-8"))
    assert next_week["weekId"] == "2026-W32"
    assert next_week["days"][0]["date"] == "2026-08-03"

    exercise_stats = json.loads((tmp_path / "exercise-stats.json").read_text(encoding="utf-8"))
    assert exercise_stats["exerciseDaysThisWeek"] == 2
    assert exercise_stats["exerciseStreak"] == 2
    assert exercise_stats["weekId"] == "2026-W31"
    assert exercise_stats["updatedAt"]

    nutrition_stats = json.loads((tmp_path / "nutrition-stats.json").read_text(encoding="utf-8"))
    assert nutrition_stats["weeklyAverage"] == {"kcal": 150.0, "protein": 9.0, "fat": 9.0, "carb": 9.5}
    assert nutrition_stats["unmatchedFoodItems"] == ["희귀채소"]
    assert nutrition_stats["disclaimer"]
    assert nutrition_stats["weekId"] == "2026-W31"
    assert nutrition_stats["updatedAt"]


def _init_repo_on_branch(repo_root, branch_name):
    subprocess.run(["git", "init", "-b", branch_name], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)
    (repo_root / "history").mkdir()
    (repo_root / "history" / "data.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", "history"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True)


def test_commit_and_push_refuses_when_not_on_main(tmp_path):
    _init_repo_on_branch(tmp_path, "feature/not-main")
    (tmp_path / "history" / "data.json").write_text('{"changed": true}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="main"):
        commit_and_push(tmp_path)


_FAKE_RESULT = {
    "weekId": "2026-W31",
    "rates": {"슬로우 조깅": 0.86, "물": 0.57},
    "adjustments": ["물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안"],
    "nextWeekId": "2026-W32",
    "exerciseDaysThisWeek": 5,
    "exerciseStreak": 3,
    "nutritionWeeklyAverage": {"kcal": 1850.0, "protein": 95.0, "fat": 65.0, "carb": 210.0},
}


def test_execute_sends_success_telegram_message_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(weekly_refresh, "run", lambda *a, **k: _FAKE_RESULT)
    monkeypatch.setattr(weekly_refresh, "commit_and_push", lambda repo_root: None)
    sent = {}
    monkeypatch.setattr(weekly_refresh, "send_telegram", lambda text: sent.setdefault("text", text))

    result = execute(tmp_path / "current-week.json", tmp_path / "history", tmp_path)

    assert result == _FAKE_RESULT
    assert "2026-W31" in sent["text"]
    assert "86%" in sent["text"]
    assert "57%" in sent["text"]
    assert "물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안" in sent["text"]
    assert "2026-W32" in sent["text"]
    assert "운동한 날: 5/7일" in sent["text"]
    assert "연속 3일째" in sent["text"]
    assert "평균 섭취(추정치): 1850kcal, 탄 210g / 지 65g / 단 95g" in sent["text"]


def test_execute_sends_failure_telegram_message_and_reraises_on_run_error(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise RuntimeError("apps script down")

    monkeypatch.setattr(weekly_refresh, "run", boom)
    sent = {}
    monkeypatch.setattr(weekly_refresh, "send_telegram", lambda text: sent.setdefault("text", text))

    with pytest.raises(RuntimeError, match="apps script down"):
        execute(tmp_path / "current-week.json", tmp_path / "history", tmp_path)

    assert "apps script down" in sent["text"]


def test_execute_sends_failure_telegram_message_on_commit_and_push_error(monkeypatch, tmp_path):
    monkeypatch.setattr(weekly_refresh, "run", lambda *a, **k: _FAKE_RESULT)

    def boom(repo_root):
        raise RuntimeError("git push rejected")

    monkeypatch.setattr(weekly_refresh, "commit_and_push", boom)
    sent = {}
    monkeypatch.setattr(weekly_refresh, "send_telegram", lambda text: sent.setdefault("text", text))

    with pytest.raises(RuntimeError, match="git push rejected"):
        execute(tmp_path / "current-week.json", tmp_path / "history", tmp_path)

    assert "git push rejected" in sent["text"]


def test_execute_notifier_failure_does_not_mask_original_error(monkeypatch, tmp_path, capsys):
    def boom(*a, **k):
        raise RuntimeError("apps script down")

    monkeypatch.setattr(weekly_refresh, "run", boom)

    def failing_notify(text):
        raise NotifierError("bad token")

    monkeypatch.setattr(weekly_refresh, "send_telegram", failing_notify)

    with pytest.raises(RuntimeError, match="apps script down"):
        execute(tmp_path / "current-week.json", tmp_path / "history", tmp_path)

    assert "bad token" in capsys.readouterr().err


def test_execute_success_survives_notifier_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(weekly_refresh, "run", lambda *a, **k: _FAKE_RESULT)
    monkeypatch.setattr(weekly_refresh, "commit_and_push", lambda repo_root: None)

    def failing_notify(text):
        raise NotifierError("bad token")

    monkeypatch.setattr(weekly_refresh, "send_telegram", failing_notify)

    result = execute(tmp_path / "current-week.json", tmp_path / "history", tmp_path)

    assert result == _FAKE_RESULT
    assert "bad token" in capsys.readouterr().err


from pathlib import Path

from weekly_refresh import person_data_dir, person_history_dir


def test_person_data_dir_is_namespaced():
    assert person_data_dir(Path("/repo"), "jammy") == Path("/repo/docs/data/jammy")


def test_person_history_dir_is_namespaced():
    assert person_history_dir(Path("/repo"), "jammy") == Path("/repo/history/jammy")
