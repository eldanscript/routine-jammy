"""주간 체크인 채점과 루틴 조정 판정 (순수 함수).

아이템 목록은 카탈로그(catalog.py)에서 오며 이 모듈에 하드코딩하지 않는다.
`logging` 타입 아이템은 체크박스가 아니라 자유 텍스트 기록이므로 완료율 집계에서
제외되고, 별도 규칙(recorded_days_by_item / find_low_logging_items)으로 판정한다.
"""

RATE_TRACKED_RULE_TYPES = ("binaryCheck", "timedPractice")


def _rate_tracked(items):
    return [item for item in items if item["ruleType"] in RATE_TRACKED_RULE_TYPES]


def completion_by_category(responses, items):
    """items 중 완료율 추적 대상(binaryCheck/timedPractice)에 대해 주간 완료율을 낸다.

    체크된 일수 / 7 로 계산하고 소수 둘째 자리에서 반올림한다. 카탈로그에 없는 아이템이
    responses에 있으면 무시한다.
    """
    totals = {item["id"]: 0 for item in _rate_tracked(items)}
    for response in responses:
        if response["item"] in totals and response["checked"]:
            totals[response["item"]] += 1
    return {item_id: round(count / 7, 2) for item_id, count in totals.items()}


def find_low_categories(current_rates, previous_rates, threshold=0.5):
    """이번 주와 지난 주가 **각각** threshold 미만인 아이템 id를 낸다.

    2주 합산이 아니라 주 단위 독립 판정이다. 지난 주 이력이 없으면 아무것도 내지 않는다.
    """
    if not previous_rates:
        return []
    low = []
    for item_id, rate in current_rates.items():
        previous_rate = previous_rates.get(item_id)
        if rate < threshold and previous_rate is not None and previous_rate < threshold:
            low.append(item_id)
    return low


def suggest_adjustments(low_ids, items):
    """low_ids 중 카탈로그에 suggestion 문구가 있는 아이템의 문구만 낸다."""
    suggestions = {
        item["id"]: item["suggestion"] for item in items if item.get("suggestion")
    }
    return [suggestions[item_id] for item_id in low_ids if item_id in suggestions]


LOGGING_MIN_DAYS = 3


def recorded_days_by_item(responses, items):
    """ruleType이 logging인 아이템에 대해, 비어있지 않은 기록이 있는 **날의 수**를 센다.

    같은 날 같은 아이템이 여러 행으로 들어와도 하루로 센다.
    """
    logging_ids = {item["id"] for item in items if item["ruleType"] == "logging"}
    days_seen = {item_id: set() for item_id in logging_ids}
    for response in responses:
        item_id = response["item"]
        if item_id not in logging_ids or not response["checked"]:
            continue
        if not response.get("note"):
            continue
        days_seen[item_id].add(response["day"])
    return {item_id: len(days) for item_id, days in days_seen.items()}


def find_low_logging_items(current_counts, previous_counts, threshold=LOGGING_MIN_DAYS):
    """이번 주와 지난 주가 **각각** threshold일 미만인 logging 아이템 id를 낸다.

    2주 합산이 아니다 — 한 주라도 threshold일 이상이면 연속이 끊긴다.
    """
    if not previous_counts:
        return []
    low = []
    for item_id, count in current_counts.items():
        previous_count = previous_counts.get(item_id)
        if count < threshold and previous_count is not None and previous_count < threshold:
            low.append(item_id)
    return low
