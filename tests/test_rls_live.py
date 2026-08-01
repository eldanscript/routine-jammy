"""RLS가 실제로 막는지 살아있는 Supabase에 대고 확인한다.

RLS는 이 설계의 유일한 보안 경계다. "정책을 안 만들어서 막힌다"는 방식이 정말 막는지
확인 없이 믿지 않는다.

실행: python3 -m pytest tests/test_rls_live.py -m network -v
필요: .env의 SUPABASE_URL, SUPABASE_SECRET_KEY, ROUTINE_JAMMY_TOKEN
"""

import os

import pytest
import requests

pytestmark = pytest.mark.network

PUBLISHABLE = "sb_publishable_sCgRLsZ5rhY32D8dJj3PKw_GPG7gyfO"
TEST_WEEK = "9999-W99"          # 실데이터와 절대 겹치지 않는 주차
TIMEOUT = 20


def _env(name):
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} 이 없어 건너뜀 (set -a; source .env; set +a 후 실행)")
    return value


@pytest.fixture
def url():
    return _env("SUPABASE_URL").rstrip("/") + "/rest/v1"


@pytest.fixture
def secret():
    return _env("SUPABASE_SECRET_KEY")


@pytest.fixture
def token():
    return _env("ROUTINE_JAMMY_TOKEN")


@pytest.fixture(autouse=True)
def cleanup(url, secret):
    """테스트가 넣은 행을 반드시 지운다."""
    yield
    requests.delete(
        f"{url}/checkins",
        params={"week_id": f"eq.{TEST_WEEK}"},
        headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
        timeout=TIMEOUT,
    )


def _row(person_id="jammy", day="월", item="검증"):
    return {
        "person_id": person_id, "week_id": TEST_WEEK, "day": day,
        "item": item, "checked": True, "payload": {},
    }


def _pub_headers(token=None):
    headers = {
        "apikey": PUBLISHABLE,
        "Authorization": f"Bearer {PUBLISHABLE}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    if token is not None:
        headers["x-routine-token"] = token
    return headers


def test_publishable_cannot_select(url):
    r = requests.get(f"{url}/checkins", params={"select": "*"},
                     headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400, "공개 키로 데이터를 읽을 수 있다"


def test_publishable_cannot_update(url):
    r = requests.patch(f"{url}/checkins", params={"id": "eq.1"},
                       json={"checked": False}, headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400


def test_publishable_cannot_delete(url):
    r = requests.delete(f"{url}/checkins", params={"id": "eq.1"},
                        headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400


def test_insert_without_token_is_denied(url):
    r = requests.post(f"{url}/checkins", json=_row(), headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400, "토큰 없이 삽입할 수 있다 — 익명 쓰기·DoS 가능"


def test_insert_with_wrong_token_is_denied(url):
    r = requests.post(f"{url}/checkins", json=_row(),
                      headers=_pub_headers("definitely-not-a-real-token"), timeout=TIMEOUT)
    assert r.status_code >= 400


def test_insert_with_own_token_succeeds(url, token):
    r = requests.post(f"{url}/checkins", json=_row(),
                      headers=_pub_headers(token), timeout=TIMEOUT)
    assert r.status_code < 300, f"정상 경로가 막혔다: {r.status_code} {r.text}"


def test_cannot_insert_as_another_person(url, token):
    """이 설계의 핵심 검사.

    with check (true) 였다면 이게 성공했을 것이고, 그건 곧 누구나 남의 이름으로 기록을
    남길 수 있다는 뜻이다 — 회고 텍스트는 공개 저장소에 커밋된다.
    """
    r = requests.post(f"{url}/checkins", json=_row(person_id="someone-else"),
                      headers=_pub_headers(token), timeout=TIMEOUT)
    assert r.status_code >= 400, "자기 토큰으로 남의 person_id를 사칭할 수 있다"


def test_cannot_forge_created_at(url, token):
    """created_at은 '최신 승자' 판정 기준이므로 클라이언트가 정할 수 없어야 한다."""
    row = {**_row(day="화"), "created_at": "2099-01-01T00:00:00Z"}
    r = requests.post(f"{url}/checkins", json=row,
                      headers=_pub_headers(token), timeout=TIMEOUT)
    assert r.status_code >= 400, "created_at을 클라이언트가 지정할 수 있다"


def test_oversized_payload_is_rejected(url, token):
    row = {**_row(day="수"), "payload": {"n": "x" * 6000}}
    r = requests.post(f"{url}/checkins", json=row,
                      headers=_pub_headers(token), timeout=TIMEOUT)
    assert r.status_code >= 400


def test_publishable_cannot_enumerate_tokens(url):
    r = requests.get(f"{url}/person_write_tokens", params={"select": "*"},
                     headers=_pub_headers(), timeout=TIMEOUT)
    assert r.status_code >= 400, "공개 키로 토큰 목록을 읽을 수 있다"


def test_secret_key_can_read(url, secret):
    r = requests.get(f"{url}/checkins", params={"select": "*", "limit": 1},
                     headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
                     timeout=TIMEOUT)
    assert r.status_code == 200, "크론이 읽지 못한다"
