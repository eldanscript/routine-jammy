import datetime

from next_week_builder import iso_week_id, shift_week


def test_iso_week_id_formats_year_and_week():
    assert iso_week_id(datetime.date(2026, 8, 3)) == "2026-W32"


def test_shift_week_moves_dates_forward_by_seven_days():
    current = {
        "weekId": "2026-W31",
        "startDate": "2026-07-27",
        "endDate": "2026-08-02",
        "days": [{"day": "월", "date": "2026-07-27", "tasks": ["슬로우 조깅", "물"]}],
    }
    next_week = shift_week(current)
    assert next_week["weekId"] == "2026-W32"
    assert next_week["startDate"] == "2026-08-03"
    assert next_week["days"][0]["date"] == "2026-08-03"
    assert next_week["days"][0]["tasks"] == ["슬로우 조깅", "물"]
