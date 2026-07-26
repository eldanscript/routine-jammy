"""Weekly automation entrypoint: pulls last week's data, updates history, and
writes next week's current-week.json. Invoked by the CronCreate job every
Sunday 18:00 Asia/Seoul (Task 8), and by the weekly-routine-refresh skill (Task 5)."""

import json
import subprocess
from pathlib import Path

from history_store import load_history, save_week, save_week_markdown
from next_week_builder import shift_week
from routine_rules import completion_by_category, find_low_categories, suggest_adjustments
from sheet_client import fetch_week


def run(current_week_path: Path, history_dir: Path, fetch_week_fn=fetch_week) -> dict:
    current_week = json.loads(current_week_path.read_text(encoding="utf-8"))
    week_id = current_week["weekId"]

    sheet_data = fetch_week_fn(week_id)
    rates = completion_by_category(sheet_data["responses"])

    history = load_history(history_dir)
    previous_week_ids = sorted(w for w in history["weeks"] if w < week_id)
    previous_rates = (
        history["weeks"][previous_week_ids[-1]]["completionByCategory"]
        if previous_week_ids
        else None
    )
    low_categories = find_low_categories(rates, previous_rates)
    adjustments = suggest_adjustments(low_categories)

    entry = {
        "completionByCategory": rates,
        "adjustmentsApplied": adjustments,
        "reflection": sheet_data.get("reflection", {}),
    }
    save_week(history_dir, week_id, entry)
    save_week_markdown(history_dir, week_id, entry)

    next_week = shift_week(current_week)
    if adjustments:
        next_week["appliedAdjustments"] = adjustments
    current_week_path.write_text(
        json.dumps(next_week, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return {
        "weekId": week_id,
        "rates": rates,
        "adjustments": adjustments,
        "nextWeekId": next_week["weekId"],
    }


def commit_and_push(repo_root: Path) -> None:
    subprocess.run(["git", "add", "history", "docs/data/current-week.json"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: weekly routine refresh\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"],
        cwd=repo_root, check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo_root, check=True)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = run(
        current_week_path=repo_root / "docs" / "data" / "current-week.json",
        history_dir=repo_root / "history",
    )
    commit_and_push(repo_root)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
