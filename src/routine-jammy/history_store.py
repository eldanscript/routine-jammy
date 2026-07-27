"""Read/write the local JSON+Markdown history mirror in history/."""

import json
from pathlib import Path

from exercise_stats import DAY_ORDER
from nutrition_lookup import NUTRITION_DISCLAIMER

_MEAL_ITEMS = ["아점", "저녁"]


def extract_meal_log(responses):
    """Extract {day: {"아점": note, "저녁": note}} from a responses list, for any
    response where item is "아점" or "저녁" and checked is true. Skip entries with
    empty/missing note."""
    meals = {}
    for response in responses:
        if response["item"] not in _MEAL_ITEMS or not response["checked"]:
            continue
        note = response.get("note")
        if not note:
            continue
        meals.setdefault(response["day"], {})[response["item"]] = note
    return meals


def load_history(history_dir: Path) -> dict:
    data_path = history_dir / "data.json"
    if not data_path.exists():
        return {"weeks": {}}
    return json.loads(data_path.read_text(encoding="utf-8"))


def save_week(history_dir: Path, week_id: str, entry: dict) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    history = load_history(history_dir)
    history["weeks"][week_id] = entry
    data_path = history_dir / "data.json"
    data_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def render_week_markdown(week_id: str, entry: dict) -> str:
    lines = [f"# {week_id} 주간 요약", "", "## 카테고리별 완료율"]
    for category, rate in entry["completionByCategory"].items():
        lines.append(f"- {category}: {round(rate * 100)}%")
    if entry.get("adjustmentsApplied"):
        lines.append("")
        lines.append("## 이번에 적용한 보완")
        for adjustment in entry["adjustmentsApplied"]:
            lines.append(f"- {adjustment}")
    exercise_days = entry.get("exerciseDaysThisWeek")
    streak = entry.get("exerciseStreak")
    if exercise_days is not None and streak is not None:
        lines.append("")
        lines.append("## 운동 요약")
        lines.append(f"- 운동한 날: {exercise_days}/7일")
        lines.append(f"- 연속 {streak}일째")
    meals = entry.get("meals")
    if meals:
        lines.append("")
        lines.append("## 식사 기록")
        for day in DAY_ORDER:
            if day not in meals:
                continue
            day_meals = meals[day]
            parts = [f"{item}: {day_meals[item]}" for item in _MEAL_ITEMS if item in day_meals]
            lines.append(f"- {day} - " + ", ".join(parts))
    nutrition = entry.get("nutrition")
    if nutrition:
        average = nutrition["weeklyAverage"]
        lines.append("")
        lines.append("## 영양 요약 (주간 평균)")
        lines.append(
            f"- {round(average['kcal'])}kcal (탄수화물 {round(average['carb'])}g / "
            f"지방 {round(average['fat'])}g / 단백질 {round(average['protein'])}g)"
        )
        if nutrition.get("recommendations"):
            for recommendation in nutrition["recommendations"]:
                lines.append(f"- {recommendation}")
        if nutrition.get("unmatchedFoodItems"):
            lines.append(f"- 매칭 실패한 재료: {', '.join(nutrition['unmatchedFoodItems'])}")
        lines.append(f"- {NUTRITION_DISCLAIMER}")
    reflection = entry.get("reflection")
    if reflection:
        lines.append("")
        lines.append("## 회고")
        lines.append(f"- 가장 잘 된 것: {reflection.get('good', '(입력 없음)')}")
        lines.append(f"- 가장 큰 방해 요인: {reflection.get('blocker', '(입력 없음)')}")
        lines.append(f"- 다음 주에 바꿀 것: {reflection.get('change', '(입력 없음)')}")
    return "\n".join(lines) + "\n"


def save_week_markdown(history_dir: Path, week_id: str, entry: dict) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    md_path = history_dir / f"{week_id}.md"
    md_path.write_text(render_week_markdown(week_id, entry), encoding="utf-8")
    return md_path
