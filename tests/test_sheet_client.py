import json

import pytest

import sheet_client


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_fetch_week_returns_parsed_json(monkeypatch):
    monkeypatch.setenv("ROUTINE_APPS_SCRIPT_URL", "https://script.google.com/macros/s/fake/exec")
    monkeypatch.setenv("ROUTINE_SHARED_SECRET", "test-secret")
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(200, {"weekId": "2026-W31", "responses": []})

    monkeypatch.setattr(sheet_client.requests, "get", fake_get)

    result = sheet_client.fetch_week("2026-W31")

    assert result == {"weekId": "2026-W31", "responses": []}
    assert captured["params"] == {"secret": "test-secret", "weekId": "2026-W31"}


def test_fetch_week_raises_on_non_200(monkeypatch):
    monkeypatch.setenv("ROUTINE_APPS_SCRIPT_URL", "https://script.google.com/macros/s/fake/exec")
    monkeypatch.setenv("ROUTINE_SHARED_SECRET", "test-secret")
    monkeypatch.setattr(
        sheet_client.requests, "get", lambda *a, **k: _FakeResponse(500, {"error": "boom"})
    )

    with pytest.raises(sheet_client.SheetClientError):
        sheet_client.fetch_week("2026-W31")


def test_fetch_week_sends_person_param(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"responses": []}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setenv("ROUTINE_APPS_SCRIPT_URL", "https://example.test/exec")
    monkeypatch.setenv("ROUTINE_SHARED_SECRET", "s3cret")
    monkeypatch.setattr("sheet_client.requests.get", fake_get)

    sheet_client.fetch_week("2026-W31", person="jammy")
    assert captured["params"]["person"] == "jammy"
    assert captured["params"]["weekId"] == "2026-W31"


def test_fetch_week_omits_person_when_not_given(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"responses": []}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setenv("ROUTINE_APPS_SCRIPT_URL", "https://example.test/exec")
    monkeypatch.setenv("ROUTINE_SHARED_SECRET", "s3cret")
    monkeypatch.setattr("sheet_client.requests.get", fake_get)

    sheet_client.fetch_week("2026-W31")
    assert "person" not in captured["params"]
    assert all(v not in (None, "") for v in captured["params"].values())


def test_fetch_week_omits_person_when_falsy(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"responses": []}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setenv("ROUTINE_APPS_SCRIPT_URL", "https://example.test/exec")
    monkeypatch.setenv("ROUTINE_SHARED_SECRET", "s3cret")
    monkeypatch.setattr("sheet_client.requests.get", fake_get)

    sheet_client.fetch_week("2026-W31", person="")
    assert "person" not in captured["params"]
    assert all(v not in (None, "") for v in captured["params"].values())
