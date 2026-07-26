"""Read/write the local JSON+Markdown history mirror in history/."""

import json
from pathlib import Path


def load_history(history_dir: Path) -> dict:
    data_path = history_dir / "data.json"
    if not data_path.exists():
        return {"weeks": {}}
    return json.loads(data_path.read_text(encoding="utf-8"))


def save_week(history_dir: Path, week_id: str, entry: dict) -> None:
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
    reflection = entry.get("reflection")
    if reflection:
        lines.append("")
        lines.append("## 회고")
        lines.append(f"- 가장 잘 된 것: {reflection.get('good', '(입력 없음)')}")
        lines.append(f"- 가장 큰 방해 요인: {reflection.get('blocker', '(입력 없음)')}")
        lines.append(f"- 다음 주에 바꿀 것: {reflection.get('change', '(입력 없음)')}")
    return "\n".join(lines) + "\n"


def save_week_markdown(history_dir: Path, week_id: str, entry: dict) -> Path:
    md_path = history_dir / f"{week_id}.md"
    md_path.write_text(render_week_markdown(week_id, entry), encoding="utf-8")
    return md_path
