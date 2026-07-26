import pytest

import telegram_notifier


class _FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def test_send_telegram_posts_correct_url_and_payload(monkeypatch):
    monkeypatch.setenv("ROUTINE_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ROUTINE_TELEGRAM_CHAT_ID", "12345")
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(200, "ok")

    monkeypatch.setattr(telegram_notifier.requests, "post", fake_post)

    telegram_notifier.send_telegram("hello")

    assert captured["url"] == "https://api.telegram.org/bottest-token/sendMessage"
    assert captured["json"] == {"chat_id": "12345", "text": "hello"}


def test_send_telegram_raises_on_non_200(monkeypatch):
    monkeypatch.setenv("ROUTINE_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ROUTINE_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(
        telegram_notifier.requests, "post", lambda *a, **k: _FakeResponse(500, "boom")
    )

    with pytest.raises(telegram_notifier.NotifierError):
        telegram_notifier.send_telegram("hello")


def test_send_telegram_sanitizes_request_exception_to_avoid_leaking_token(monkeypatch):
    monkeypatch.setenv("ROUTINE_TELEGRAM_BOT_TOKEN", "super-secret-token")
    monkeypatch.setenv("ROUTINE_TELEGRAM_CHAT_ID", "12345")

    def fake_post(url, json, timeout):
        raise telegram_notifier.requests.exceptions.ConnectionError(
            f"Max retries exceeded with url: /botsuper-secret-token/sendMessage (url={url})"
        )

    monkeypatch.setattr(telegram_notifier.requests, "post", fake_post)

    with pytest.raises(telegram_notifier.NotifierError) as excinfo:
        telegram_notifier.send_telegram("hello")

    assert "super-secret-token" not in str(excinfo.value)
