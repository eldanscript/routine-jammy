"""Estimate meal macronutrients by matching free-text meal segments against the
Korean government's 식품영양성분DB (data.go.kr FoodNtrCpntDbInfo02) API."""

import os
import re

import requests

_QUANTITY_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(g|그램|kg)")
_VAGUE_QUANTITY_PATTERN = re.compile(r"\s*(조금|약간|적당량|많이)\s*$")
_DEFAULT_GRAMS = 100.0

_KCAL_PER_GRAM = {"carb": 4, "protein": 4, "fat": 9}
_AMDR_RANGES = {"carb": (0.45, 0.65), "fat": (0.20, 0.35), "protein": (0.10, 0.35)}
_LOW_RECOMMENDATIONS = {
    "carb": "탄수화물 비중이 낮은 편이에요 — 밥이나 잡곡 등 탄수화물 섭취를 조금 늘려보세요",
    "fat": "지방 비중이 낮은 편이에요 — 견과류나 오일 등 좋은 지방을 조금 늘려보세요",
    "protein": "단백질 비중이 낮은 편이에요 — 단백질 식품표를 참고해서 늘려보세요",
}
_HIGH_RECOMMENDATIONS = {
    "carb": "탄수화물 비중이 높은 편이에요 — 정제 탄수화물 섭취를 조금 줄여보세요",
    "fat": "지방 비중이 높은 편이에요 — 튀김/기름진 음식을 조금 줄여보세요",
    "protein": "단백질 비중이 높은 편이에요 — 다른 영양소와 균형을 맞춰보는 걸 추천해요",
}
_MAX_RECOMMENDATIONS = 2

NUTRITION_DISCLAIMER = (
    "⚠️ 영양 수치는 식약처 공공 데이터베이스 자동 매칭 기반의 대략적 추정치입니다 "
    "(재료명이 가공식품/메뉴로 잘못 매칭될 수 있음)."
)


class NutritionLookupError(RuntimeError):
    pass


def parse_meal_segments(meal_text):
    """Split free text like "닭가슴살 100g + 두부 조금 + 채소" on "+" into segments.
    For each segment, extract a gram quantity if present (converting kg to g), else
    None. Returns a list of {"raw": str, "food_name": str, "grams": float | None}.
    food_name is the segment with the matched quantity substring removed and stripped
    of surrounding whitespace; vague non-numeric quantity words (e.g. "조금") are also
    stripped so the remaining text matches better against the nutrition DB. Skip/ignore
    empty segments (e.g. trailing "+")."""
    segments = []
    for raw in meal_text.split("+"):
        raw = raw.strip()
        if not raw:
            continue
        match = _QUANTITY_PATTERN.search(raw)
        if match:
            value, unit = match.groups()
            grams = float(value) * 1000 if unit == "kg" else float(value)
            food_name = _QUANTITY_PATTERN.sub("", raw, count=1).strip()
        else:
            grams = None
            food_name = _VAGUE_QUANTITY_PATTERN.sub("", raw).strip()
        segments.append({"raw": raw, "food_name": food_name, "grams": grams})
    return segments


def _serving_size_grams(serving_size):
    match = _QUANTITY_PATTERN.search(serving_size or "")
    if not match:
        return _DEFAULT_GRAMS
    value, unit = match.groups()
    return float(value) * 1000 if unit == "kg" else float(value)


def _score_candidate(item, food_name):
    """Score how well an item's FOOD_NM_KR matches `food_name`, higher is better.
    This DB is dish/product-centric (e.g. "샌드위치_닭가슴살", "두부찌개") rather than a
    raw-ingredient database, so an exact match is rare — this heuristic prefers an
    exact match, then a compound name where `food_name` is one of its "_"/space
    separated tokens (shorter compounds preferred), then falls back to preferring
    shorter names generally over long branded/menu names."""
    name = item.get("FOOD_NM_KR", "")
    if name == food_name:
        return 100
    tokens = name.replace(" ", "_").split("_")
    if food_name in tokens:
        return 50 - len(name)
    return -len(name)


def fetch_nutrition_per_100g(food_name, endpoint=None, api_key=None):
    """Query the API for `food_name`, return {"kcal": float, "protein": float,
    "fat": float, "carb": float} per 100g of the best-scoring match (see
    _score_candidate), or None if no match (totalCount == 0). Reads
    ROUTINE_NUTRITION_API_ENDPOINT/ROUTINE_NUTRITION_API_KEY from env if
    endpoint/api_key aren't passed explicitly. Raise NutritionLookupError on any
    failure mode of the external call or its response — non-200 HTTP response, a
    network-level failure (timeout, connection error), or ANY problem while parsing/
    scoring/scaling the response body (invalid JSON, a non-"00" resultCode, missing
    keys, non-numeric fields, division by a zero serving size, etc.) — so callers can
    rely on catching just this one exception type, never a raw requests/json/KeyError/
    ZeroDivisionError escaping from here."""
    endpoint = endpoint or os.environ["ROUTINE_NUTRITION_API_ENDPOINT"]
    api_key = api_key or os.environ["ROUTINE_NUTRITION_API_KEY"]
    try:
        response = requests.get(
            f"{endpoint}/getFoodNtrCpntDbInq02",
            params={
                "serviceKey": api_key,
                "FOOD_NM_KR": food_name,
                "numOfRows": 20,
                "pageNo": 1,
                "type": "json",
            },
            timeout=15,
        )
    except requests.exceptions.RequestException as error:
        raise NutritionLookupError(
            f"Nutrition API request failed: {type(error).__name__}"
        ) from None
    if response.status_code != 200:
        raise NutritionLookupError(
            f"Nutrition API GET failed with status {response.status_code}: {response.text}"
        )
    try:
        payload = response.json()
        result_code = payload["header"]["resultCode"]
        if result_code != "00":
            raise NutritionLookupError(
                f"Nutrition API returned resultCode {result_code}: "
                f"{payload['header'].get('resultMsg', '(no message)')}"
            )
        body = payload["body"]
        if body["totalCount"] == 0:
            return None
        item = max(body["items"], key=lambda candidate: _score_candidate(candidate, food_name))
        scale = 100.0 / _serving_size_grams(item.get("SERVING_SIZE"))
        return {
            "kcal": float(item["AMT_NUM1"]) * scale,
            "protein": float(item["AMT_NUM3"]) * scale,
            "fat": float(item["AMT_NUM4"]) * scale,
            "carb": float(item["AMT_NUM6"]) * scale,
        }
    except NutritionLookupError:
        raise  # already the right exception type, don't re-wrap
    except Exception as error:
        raise NutritionLookupError(
            f"Nutrition API response could not be processed: {type(error).__name__}: {error}"
        ) from None


def estimate_meal_nutrition(meal_text, lookup_fn=fetch_nutrition_per_100g):
    """Parse `meal_text` into segments, look up each resolvable one, and sum
    kcal/protein/fat/carb scaled by grams/100 (defaulting to 100g when a segment has
    no explicit quantity). Returns:
    {"kcal": float, "protein": float, "fat": float, "carb": float,
     "matchedItems": [{"food_name": str, "grams": float}, ...],
     "unmatchedItems": [str, ...]}  # food names that had no DB match, or lookup failed
    A segment with no DB match does not raise — it's added to unmatchedItems and the
    rest of the calculation continues."""
    totals = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carb": 0.0}
    matched_items = []
    unmatched_items = []
    for segment in parse_meal_segments(meal_text):
        if not segment["food_name"]:
            unmatched_items.append(segment["raw"])
            continue
        grams = segment["grams"] if segment["grams"] is not None else _DEFAULT_GRAMS
        try:
            nutrition = lookup_fn(segment["food_name"])
        except NutritionLookupError:
            nutrition = None
        if nutrition is None:
            unmatched_items.append(segment["food_name"])
            continue
        scale = grams / 100.0
        for key in totals:
            totals[key] += nutrition[key] * scale
        matched_items.append({"food_name": segment["food_name"], "grams": grams})
    return {**totals, "matchedItems": matched_items, "unmatchedItems": unmatched_items}


def weekly_macro_recommendations(weekly_average):
    """Compare `weekly_average`'s carb/fat/protein grams (converted to % of total
    kcal via 4/4/9 kcal-per-gram) against AMDR ranges, and return 0-2 short
    Korean-language observations (checked in carb, fat, protein order) for macros
    that fall outside their range. Returns [] if total kcal is 0 (no data)."""
    macro_kcal = {macro: weekly_average[macro] * _KCAL_PER_GRAM[macro] for macro in _KCAL_PER_GRAM}
    total_kcal = sum(macro_kcal.values())
    if total_kcal <= 0:
        return []
    recommendations = []
    for macro in ("carb", "fat", "protein"):
        low, high = _AMDR_RANGES[macro]
        percentage = macro_kcal[macro] / total_kcal
        if percentage < low:
            recommendations.append(_LOW_RECOMMENDATIONS[macro])
        elif percentage > high:
            recommendations.append(_HIGH_RECOMMENDATIONS[macro])
    return recommendations[:_MAX_RECOMMENDATIONS]
