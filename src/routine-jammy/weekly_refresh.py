"""Weekly automation entrypoint: pulls last week's data, updates history, and
writes next week's current-week.json. Invoked by a plain OS crontab entry every
Sunday 18:00 Asia/Seoul (Task 8), and by the weekly-routine-refresh skill (Task 5)."""

import json
import subprocess
import sys
from pathlib import Path

from exercise_stats import build_day_level, days_with_any_exercise, exercised_sequence, longest_current_streak
from history_store import extract_meal_log, load_history, save_week, save_week_markdown
from next_week_builder import shift_week
from routine_rules import completion_by_category, find_low_categories, suggest_adjustments
from sheet_client import fetch_week
from telegram_notifier import send_telegram


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

    day_level = build_day_level(sheet_data["responses"])
    meals = extract_meal_log(sheet_data["responses"])
    exercise_days = days_with_any_exercise(day_level)
    streak = longest_current_streak(exercised_sequence(history, week_id, day_level))

    entry = {
        "completionByCategory": rates,
        "adjustmentsApplied": adjustments,
        "reflection": sheet_data.get("reflection", {}),
        "byDay": day_level,
        "meals": meals,
        "exerciseDaysThisWeek": exercise_days,
        "exerciseStreak": streak,
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
        "exerciseDaysThisWeek": exercise_days,
        "exerciseStreak": streak,
    }


def commit_and_push(repo_root: Path) -> None:
    current_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if current_branch != "main":
        raise RuntimeError(
            f"refusing to commit_and_push: expected branch 'main', found '{current_branch}'"
        )
    subprocess.run(["git", "add", "history", "docs/data/current-week.json"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: weekly routine refresh\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"],
        cwd=repo_root, check=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo_root, check=True)


def build_success_message(result: dict) -> str:
    lines = [f"루틴 주간 리프레시 완료 — {result['weekId']}"]
    lines.append("완료율: " + ", ".join(
        f"{category} {round(rate * 100)}%" for category, rate in result["rates"].items()
    ))
    if result["adjustments"]:
        lines.append("조정 제안:")
        lines.extend(f"- {adjustment}" for adjustment in result["adjustments"])
    lines.append(
        f"운동한 날: {result['exerciseDaysThisWeek']}/7일, 연속 {result['exerciseStreak']}일째"
    )
    lines.append(f"다음 주({result['nextWeekId']}) 루틴이 배포되었습니다.")
    return "\n".join(lines)


def build_failure_message(error: Exception) -> str:
    return f"루틴 주간 리프레시 실패: {error}"


def notify(text: str) -> None:
    try:
        send_telegram(text)
    except Exception as error:
        print(f"Telegram notification failed: {error}", file=sys.stderr)


def execute(current_week_path: Path, history_dir: Path, repo_root: Path) -> dict:
    try:
        result = run(current_week_path, history_dir)
        commit_and_push(repo_root)
    except Exception as error:
        notify(build_failure_message(error))
        raise
    notify(build_success_message(result))
    return result


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = execute(
        current_week_path=repo_root / "docs" / "data" / "current-week.json",
        history_dir=repo_root / "history",
        repo_root=repo_root,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
