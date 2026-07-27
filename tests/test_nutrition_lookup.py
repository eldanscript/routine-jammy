import json

import pytest

import nutrition_lookup
from nutrition_lookup import (
    NutritionLookupError,
    estimate_meal_nutrition,
    fetch_nutrition_per_100g,
    parse_meal_segments,
    weekly_macro_recommendations,
)


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _rice_payload(result_code="00", total_count=1):
    return {
        "header": {"resultCode": result_code, "resultMsg": "NORMAL SERVICE."},
        "body": {
            "pageNo": 1,
            "totalCount": total_count,
            "numOfRows": 20,
            "items": [
                {
                    "FOOD_NM_KR": "쌀밥",
                    "SERVING_SIZE": "100g",
                    "AMT_NUM1": "166.000",
                    "AMT_NUM2": "58.90",
                    "AMT_NUM3": "3.36",
                    "AMT_NUM4": "0.32",
                    "AMT_NUM5": "0.11",
                    "AMT_NUM6": "37.33",
                    "AMT_NUM7": "0.02",
                    "AMT_NUM8": "0.10",
                }
            ],
        },
    }


def test_parse_meal_segments_splits_and_extracts_quantities():
    segments = parse_meal_segments("닭가슴살 100g + 두부 조금 + 채소")

    assert len(segments) == 3
    assert segments[0]["food_name"] == "닭가슴살"
    assert segments[0]["grams"] == 100.0
    assert segments[1]["food_name"] == "두부"
    assert segments[1]["grams"] is None
    assert segments[2]["food_name"] == "채소"
    assert segments[2]["grams"] is None


def test_parse_meal_segments_converts_kg_to_grams():
    segments = parse_meal_segments("현미밥 1kg")

    assert len(segments) == 1
    assert segments[0]["food_name"] == "현미밥"
    assert segments[0]["grams"] == 1000.0


def test_parse_meal_segments_single_segment_without_plus():
    segments = parse_meal_segments("계란볶음밥")

    assert len(segments) == 1
    assert segments[0]["food_name"] == "계란볶음밥"
    assert segments[0]["grams"] is None


def test_parse_meal_segments_handles_extra_whitespace_around_plus():
    segments = parse_meal_segments("닭가슴살 100g   +   두부")

    assert len(segments) == 2
    assert segments[0]["food_name"] == "닭가슴살"
    assert segments[1]["food_name"] == "두부"


def test_parse_meal_segments_skips_empty_segments():
    segments = parse_meal_segments("닭가슴살 100g + ")

    assert len(segments) == 1
    assert segments[0]["food_name"] == "닭가슴살"


def test_fetch_nutrition_per_100g_maps_verified_columns(monkeypatch):
    monkeypatch.setenv("ROUTINE_NUTRITION_API_ENDPOINT", "https://fake.data.go.kr/api")
    monkeypatch.setenv("ROUTINE_NUTRITION_API_KEY", "test-key")
    monkeypatch.setattr(
        nutrition_lookup.requests, "get", lambda *a, **k: _FakeResponse(200, _rice_payload())
    )

    result = fetch_nutrition_per_100g("쌀밥")

    assert result == {"kcal": 166.0, "protein": 3.36, "fat": 0.32, "carb": 37.33}


def test_fetch_nutrition_per_100g_prefers_exact_match_over_partial(monkeypatch):
    monkeypatch.setenv("ROUTINE_NUTRITION_API_ENDPOINT", "https://fake.data.go.kr/api")
    monkeypatch.setenv("ROUTINE_NUTRITION_API_KEY", "test-key")
    payload = {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {
            "pageNo": 1,
            "totalCount": 3,
            "numOfRows": 20,
            "items": [
                {
                    "FOOD_NM_KR": "샌드위치_닭가슴살",
                    "SERVING_SIZE": "100g",
                    "AMT_NUM1": "240.000",
                    "AMT_NUM3": "12.18",
                    "AMT_NUM4": "11.92",
                    "AMT_NUM6": "20.96",
                },
                {
                    "FOOD_NM_KR": "닭가슴살",
                    "SERVING_SIZE": "100g",
                    "AMT_NUM1": "109.000",
                    "AMT_NUM3": "23.30",
                    "AMT_NUM4": "1.30",
                    "AMT_NUM6": "0.00",
                },
                {
                    "FOOD_NM_KR": "닭가슴살_핫도그",
                    "SERVING_SIZE": "100g",
                    "AMT_NUM1": "280.000",
                    "AMT_NUM3": "10.00",
                    "AMT_NUM4": "18.00",
                    "AMT_NUM6": "22.00",
                },
            ],
        },
    }
    monkeypatch.setattr(
        nutrition_lookup.requests, "get", lambda *a, **k: _FakeResponse(200, payload)
    )

    result = fetch_nutrition_per_100g("닭가슴살")

    assert result == {"kcal": 109.0, "protein": 23.30, "fat": 1.30, "carb": 0.00}


def test_fetch_nutrition_per_100g_returns_none_when_no_match(monkeypatch):
    monkeypatch.setenv("ROUTINE_NUTRITION_API_ENDPOINT", "https://fake.data.go.kr/api")
    monkeypatch.setenv("ROUTINE_NUTRITION_API_KEY", "test-key")
    payload = _rice_payload(total_count=0)
    payload["body"]["items"] = []
    monkeypatch.setattr(
        nutrition_lookup.requests, "get", lambda *a, **k: _FakeResponse(200, payload)
    )

    assert fetch_nutrition_per_100g("존재하지않는음식") is None


def test_fetch_nutrition_per_100g_raises_on_connection_error(monkeypatch):
    monkeypatch.setenv("ROUTINE_NUTRITION_API_ENDPOINT", "https://fake.data.go.kr/api")
    monkeypatch.setenv("ROUTINE_NUTRITION_API_KEY", "test-key")

    def raise_connection_error(*a, **k):
        raise nutrition_lookup.requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(nutrition_lookup.requests, "get", raise_connection_error)

    with pytest.raises(NutritionLookupError):
        fetch_nutrition_per_100g("쌀밥")


def test_fetch_nutrition_per_100g_raises_on_non_200(monkeypatch):
    monkeypatch.setenv("ROUTINE_NUTRITION_API_ENDPOINT", "https://fake.data.go.kr/api")
    monkeypatch.setenv("ROUTINE_NUTRITION_API_KEY", "test-key")
    monkeypatch.setattr(
        nutrition_lookup.requests, "get", lambda *a, **k: _FakeResponse(500, {"error": "boom"})
    )

    with pytest.raises(NutritionLookupError):
        fetch_nutrition_per_100g("쌀밥")


def test_fetch_nutrition_per_100g_raises_on_non_00_result_code(monkeypatch):
    monkeypatch.setenv("ROUTINE_NUTRITION_API_ENDPOINT", "https://fake.data.go.kr/api")
    monkeypatch.setenv("ROUTINE_NUTRITION_API_KEY", "test-key")
    payload = {
        "header": {"resultCode": "99", "resultMsg": "SERVICE ERROR."},
        "body": {},
    }
    monkeypatch.setattr(
        nutrition_lookup.requests, "get", lambda *a, **k: _FakeResponse(200, payload)
    )

    with pytest.raises(NutritionLookupError):
        fetch_nutrition_per_100g("쌀밥")


def test_fetch_nutrition_per_100g_raises_on_non_00_result_code_without_result_msg(monkeypatch):
    monkeypatch.setenv("ROUTINE_NUTRITION_API_ENDPOINT", "https://fake.data.go.kr/api")
    monkeypatch.setenv("ROUTINE_NUTRITION_API_KEY", "test-key")
    payload = {
        "header": {"resultCode": "99"},
        "body": {},
    }
    monkeypatch.setattr(
        nutrition_lookup.requests, "get", lambda *a, **k: _FakeResponse(200, payload)
    )

    with pytest.raises(NutritionLookupError, match="no message"):
        fetch_nutrition_per_100g("쌀밥")


def test_fetch_nutrition_per_100g_raises_on_zero_serving_size(monkeypatch):
    monkeypatch.setenv("ROUTINE_NUTRITION_API_ENDPOINT", "https://fake.data.go.kr/api")
    monkeypatch.setenv("ROUTINE_NUTRITION_API_KEY", "test-key")
    payload = _rice_payload()
    payload["body"]["items"][0]["SERVING_SIZE"] = "0g"
    monkeypatch.setattr(
        nutrition_lookup.requests, "get", lambda *a, **k: _FakeResponse(200, payload)
    )

    with pytest.raises(NutritionLookupError):
        fetch_nutrition_per_100g("쌀밥")


def test_estimate_meal_nutrition_scales_by_grams():
    def fake_lookup(food_name):
        return {"kcal": 200.0, "protein": 20.0, "fat": 10.0, "carb": 5.0}

    result = estimate_meal_nutrition("닭가슴살 50g", lookup_fn=fake_lookup)

    assert result["kcal"] == 100.0
    assert result["protein"] == 10.0
    assert result["fat"] == 5.0
    assert result["carb"] == 2.5
    assert result["matchedItems"] == [{"food_name": "닭가슴살", "grams": 50.0}]
    assert result["unmatchedItems"] == []


def test_estimate_meal_nutrition_defaults_to_100g_when_unquantified():
    def fake_lookup(food_name):
        return {"kcal": 100.0, "protein": 10.0, "fat": 5.0, "carb": 15.0}

    result = estimate_meal_nutrition("채소", lookup_fn=fake_lookup)

    assert result["kcal"] == 100.0
    assert result["matchedItems"] == [{"food_name": "채소", "grams": 100.0}]


def test_weekly_macro_recommendations_returns_empty_when_all_in_range():
    weekly_average = {"kcal": 1000.0, "carb": 137.5, "fat": 30.0, "protein": 45.0}

    assert weekly_macro_recommendations(weekly_average) == []


def test_weekly_macro_recommendations_flags_low_protein():
    weekly_average = {"kcal": 1000.0, "carb": 145.0, "fat": 37.777777, "protein": 20.0}

    result = weekly_macro_recommendations(weekly_average)

    assert result == ["단백질 비중이 낮은 편이에요 — 단백질 식품표를 참고해서 늘려보세요"]


def test_weekly_macro_recommendations_flags_multiple_macros_in_order():
    weekly_average = {"kcal": 1000.0, "carb": 175.0, "fat": 24.444444, "protein": 20.0}

    result = weekly_macro_recommendations(weekly_average)

    assert result == [
        "탄수화물 비중이 높은 편이에요 — 정제 탄수화물 섭취를 조금 줄여보세요",
        "단백질 비중이 낮은 편이에요 — 단백질 식품표를 참고해서 늘려보세요",
    ]


def test_weekly_macro_recommendations_caps_at_two():
    weekly_average = {"kcal": 1000.0, "carb": 190.0, "fat": 16.666667, "protein": 22.5}

    result = weekly_macro_recommendations(weekly_average)

    assert len(result) == 2
    assert result == [
        "탄수화물 비중이 높은 편이에요 — 정제 탄수화물 섭취를 조금 줄여보세요",
        "지방 비중이 낮은 편이에요 — 견과류나 오일 등 좋은 지방을 조금 늘려보세요",
    ]


def test_estimate_meal_nutrition_treats_network_failure_as_unmatched(monkeypatch):
    monkeypatch.setenv("ROUTINE_NUTRITION_API_ENDPOINT", "https://fake.data.go.kr/api")
    monkeypatch.setenv("ROUTINE_NUTRITION_API_KEY", "test-key")

    def raise_connection_error(*a, **k):
        raise nutrition_lookup.requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(nutrition_lookup.requests, "get", raise_connection_error)

    result = estimate_meal_nutrition("닭가슴살 100g")

    assert result["kcal"] == 0.0
    assert result["unmatchedItems"] == ["닭가슴살"]
    assert result["matchedItems"] == []


def test_estimate_meal_nutrition_skips_segments_with_empty_food_name():
    def fake_lookup(food_name):
        raise AssertionError("should not be called for an empty food name")

    result = estimate_meal_nutrition("100g", lookup_fn=fake_lookup)

    assert result["kcal"] == 0.0
    assert result["unmatchedItems"] == ["100g"]
    assert result["matchedItems"] == []


def test_estimate_meal_nutrition_collects_unmatched_without_crashing():
    def fake_lookup(food_name):
        if food_name == "닭가슴살":
            return {"kcal": 200.0, "protein": 20.0, "fat": 10.0, "carb": 5.0}
        return None

    result = estimate_meal_nutrition("닭가슴살 100g + 알수없는재료", lookup_fn=fake_lookup)

    assert result["kcal"] == 200.0
    assert result["unmatchedItems"] == ["알수없는재료"]
    assert result["matchedItems"] == [{"food_name": "닭가슴살", "grams": 100.0}]
