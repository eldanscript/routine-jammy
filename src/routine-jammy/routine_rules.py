"""Pure functions for scoring a week's check-ins and deciding routine adjustments."""

CATEGORIES = ["슬로우 조깅", "스쿼트", "데드리프트", "런지", "플랭크", "간식섭취", "바이올린"]

_SUGGESTIONS = {
    "바이올린": "바이올린 연습 시간을 줄여서 꾸준히 이어가는 걸 제안",
    "간식섭취": "간식섭취 체크 기준을 더 쉽게 낮추는 걸 제안",
}


def completion_by_category(responses):
    totals = {category: 0 for category in CATEGORIES}
    for response in responses:
        if response["item"] in totals and response["checked"]:
            totals[response["item"]] += 1
    return {category: round(count / 7, 2) for category, count in totals.items()}


def find_low_categories(current_rates, previous_rates, threshold=0.5):
    if not previous_rates:
        return []
    low = []
    for category, rate in current_rates.items():
        previous_rate = previous_rates.get(category)
        if rate < threshold and previous_rate is not None and previous_rate < threshold:
            low.append(category)
    return low


def suggest_adjustments(low_categories):
    return [_SUGGESTIONS[category] for category in low_categories if category in _SUGGESTIONS]
