"""Supabase 무료 티어 일시정지 방지용 일일 keepalive.

무료 플랜은 7일간 DB 활동이 부족하면 프로젝트를 정지시킨다. 주간 크론(7일에 한 번)만으로는
경계선에 걸리고, 정지되면 하필 그 주간 리프레시가 실패한다. 그래서 매일 가장 싼 쿼리를
한 번 날린다.

주간 리프레시와 별도 크론 엔트리로 돈다 — 주간 작업이 실패해도 이것까지 같이 죽으면 안 된다.
실패는 조용히 넘기지 않는다: 실패했다는 것은 이미 정지됐거나 곧 정지된다는 신호다.
"""

import os
import sys

import requests

from telegram_notifier import send_telegram

_TIMEOUT = 15


def ping() -> int:
    """가장 싼 쿼리 1회. 성공하면 반환된 행 수를 낸다."""
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SECRET_KEY"]
    response = requests.get(
        f"{base_url}/rest/v1/checkins",
        params={"select": "id", "limit": 1},
        headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
        timeout=_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Supabase health check failed with status {response.status_code}: {response.text}"
        )
    return len(response.json())


def main() -> None:
    try:
        ping()
    except Exception as error:
        message = (
            "Supabase health check 실패 — 프로젝트가 일시정지됐거나 곧 정지될 수 있습니다.\n"
            f"{error}\n"
            "대시보드에서 Restore project가 필요한지 확인하세요."
        )
        try:
            send_telegram(message)
        except Exception as notify_error:
            print(f"Telegram notification failed: {notify_error}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
