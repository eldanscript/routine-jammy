import json
import subprocess

import pytest

from weekly_refresh import commit_and_push, run


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
