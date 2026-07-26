"""Thin HTTP client for the Apps Script web app backing the Google Sheet."""

import os

import requests


class SheetClientError(RuntimeError):
    pass


def fetch_week(week_id: str) -> dict:
    """GET the given week's check-in responses from the Apps Script web app.

    Requires ROUTINE_APPS_SCRIPT_URL and ROUTINE_SHARED_SECRET env vars.
    """
    base_url = os.environ["ROUTINE_APPS_SCRIPT_URL"]
    secret = os.environ["ROUTINE_SHARED_SECRET"]
    response = requests.get(
        base_url, params={"secret": secret, "weekId": week_id}, timeout=15
    )
    if response.status_code != 200:
        raise SheetClientError(
            f"Apps Script GET failed with status {response.status_code}: {response.text}"
        )
    return response.json()
