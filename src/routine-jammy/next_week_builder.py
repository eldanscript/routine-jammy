"""Builds next week's current-week.json from this week's template."""

import datetime


def iso_week_id(date: datetime.date) -> str:
    year, week, _ = date.isocalendar()
    return f"{year}-W{week:02d}"


def shift_week(current_week: dict) -> dict:
    start = datetime.date.fromisoformat(current_week["startDate"]) + datetime.timedelta(days=7)
    end = datetime.date.fromisoformat(current_week["endDate"]) + datetime.timedelta(days=7)
    new_days = []
    for day in current_week["days"]:
        old_date = datetime.date.fromisoformat(day["date"])
        new_date = old_date + datetime.timedelta(days=7)
        new_days.append({**day, "date": new_date.isoformat()})
    return {
        "weekId": iso_week_id(start),
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "days": new_days,
    }
