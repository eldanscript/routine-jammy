import pytest
from health_check import ping


def test_ping_returns_row_count(monkeypatch):
    class FakeResponse:
        status_code = 200
        def json(self):
            return [{"id": 1}]

    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setattr("health_check.requests.get", lambda *a, **k: FakeResponse())
    assert ping() == 1


def test_ping_raises_on_error(monkeypatch):
    class FakeResponse:
        status_code = 503
        text = "paused"
        def json(self):
            return {}

    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setattr("health_check.requests.get", lambda *a, **k: FakeResponse())
    with pytest.raises(RuntimeError, match="503"):
        ping()
