"""Pure functions for exercise frequency, streak, and day-of-week pattern analysis
across a single week's responses and the accumulated multi-week history."""

DAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]


def build_day_level(responses):
    """responses: list of {day, item, checked, ...}. Returns {day: {item: bool}},
    only for items that were actually checked=true or checked=false (skip malformed rows)."""
    by_day = {}
    for response in responses:
        by_day.setdefault(response["day"], {})[response["item"]] = bool(response["checked"])
    return by_day


def _day_has_exercise(items, exercise_ids):
    return any(items.get(item_id) for item_id in exercise_ids)


def days_with_any_exercise(day_level, exercise_ids):
    """day_level에 존재하는 날 중, exercise_ids 가운데 하나라도 True인 날의 수."""
    return sum(1 for items in day_level.values() if _day_has_exercise(items, exercise_ids))


def exercised_sequence(history, current_week_id, current_day_level, exercise_ids):
    """Build a chronological list of booleans (one per day, oldest first) — whether
    ANY exercise category was checked that day — across all weeks in `history["weeks"]`
    with weekId < current_week_id (sorted ascending), followed by the current week's
    `current_day_level`. Each week's days are ordered per DAY_ORDER; a week entry must
    have a "byDay" key (dict shaped like build_day_level's output) to contribute — skip
    weeks that don't have one (e.g. archived before this feature existed) rather than
    raising."""
    archived_week_ids = sorted(
        week_id for week_id, entry in history["weeks"].items()
        if week_id < current_week_id and "byDay" in entry
    )
    sequence = []
    for week_id in archived_week_ids:
        day_level = history["weeks"][week_id]["byDay"]
        for day in DAY_ORDER:
            if day in day_level:
                sequence.append(_day_has_exercise(day_level[day], exercise_ids))
    for day in DAY_ORDER:
        if day in current_day_level:
            sequence.append(_day_has_exercise(current_day_level[day], exercise_ids))
    return sequence


def longest_current_streak(sequence):
    """Longest trailing run of True values at the END of `sequence` (a list of bools).
    Returns 0 if the sequence is empty or ends in False."""
    streak = 0
    for value in reversed(sequence):
        if not value:
            break
        streak += 1
    return streak


def rolling_completion_average(history, category, current_week_id, current_rate, num_weeks=4):
    """Average completion rate for `category` over the most recent `num_weeks` weeks
    (weeks with weekId <= current_week_id, most recent first, including the current
    week's own `current_rate` for `category` as the most recent data point), using
    each archived week's "completionByCategory" dict. Weeks missing that category key
    are skipped. Returns None if no data points are available at all."""
    archived_week_ids = sorted(
        week_id for week_id, entry in history["weeks"].items()
        if week_id < current_week_id and category in entry.get("completionByCategory", {})
    )
    rates = [history["weeks"][week_id]["completionByCategory"][category] for week_id in archived_week_ids]
    if current_rate is not None:
        rates.append(current_rate)
    recent = rates[-num_weeks:]
    return sum(recent) / len(recent) if recent else None


def category_skip_pattern(history, current_week_id, current_day_level, exercise_ids):
    """Across ALL weeks with weekId <= current_week_id that have a "byDay" key (including
    the current week via `current_day_level`), count how many times each (day, category)
    combination in exercise_ids was checked False (explicitly present and false,
    OR simply absent from that day's dict — both count as "not done"). Returns
    {day: {category: skip_count}} for all 7 DAY_ORDER days and all exercise_ids,
    even if some counts are 0."""
    pattern = {day: {category: 0 for category in exercise_ids} for day in DAY_ORDER}

    archived_week_ids = sorted(
        week_id for week_id, entry in history["weeks"].items()
        if week_id < current_week_id and "byDay" in entry
    )
    day_levels = [history["weeks"][week_id]["byDay"] for week_id in archived_week_ids]
    day_levels.append(current_day_level)

    for day_level in day_levels:
        for day in DAY_ORDER:
            if day not in day_level:
                continue
            items = day_level[day]
            for category in exercise_ids:
                if not items.get(category):
                    pattern[day][category] += 1

    return pattern
