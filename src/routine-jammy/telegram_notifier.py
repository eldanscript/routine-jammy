"""Thin HTTP client for sending weekly summary notifications via Telegram."""

import os

import requests


class NotifierError(RuntimeError):
    pass


def send_telegram(text: str) -> None:
    """POST a message to the configured Telegram chat.

    Requires ROUTINE_TELEGRAM_BOT_TOKEN and ROUTINE_TELEGRAM_CHAT_ID env vars.
    """
    token = os.environ["ROUTINE_TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["ROUTINE_TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
    if response.status_code != 200:
        raise NotifierError(
            f"Telegram sendMessage failed with status {response.status_code}: {response.text}"
        )
