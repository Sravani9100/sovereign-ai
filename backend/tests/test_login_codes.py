"""Email sign-in codes (one-time passwords)."""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from sovereign.db import system_session
from sovereign.demo import USERS
from sovereign.models import LoginCode, utcnow

BEN = USERS["ben"][0]


@pytest.fixture(autouse=True)
def clean(world):
    with system_session(world.sessions) as session:
        session.execute(delete(LoginCode))
        session.commit()
    world.mailer.sent.clear()


def request_code(client: TestClient, email: str):
    return client.post("/api/v1/auth/code", json={"email": email})


def last_code(world) -> str:
    _to, subject, _body = world.mailer.sent[-1]
    return re.search(r"\b(\d{6})\b", subject).group(1)


def verify(client: TestClient, email: str, code: str):
    return client.post("/api/v1/auth/code/verify", json={"email": email, "code": code})


def test_known_and_unknown_addresses_get_the_same_response(world):
    client = TestClient(world.app)
    known = request_code(client, BEN)
    unknown = request_code(client, "nobody@musterwerk.example")
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [to for to, _, _ in world.mailer.sent] == [BEN]


def test_code_signs_in_once(world):
    client = TestClient(world.app)
    request_code(client, BEN.upper())  # addresses are case-insensitive
    code = last_code(world)

    response = verify(client, BEN, code)
    assert response.status_code == 200
    assert response.json()["email"] == BEN
    assert client.get("/api/v1/auth/me").status_code == 200  # the session cookie works

    assert verify(TestClient(world.app), BEN, code).status_code == 401  # single use


def test_codes_are_stored_hashed(world):
    request_code(TestClient(world.app), BEN)
    code = last_code(world)
    with system_session(world.sessions) as session:
        stored = session.scalar(select(LoginCode.code_hash))
    assert code not in stored
    assert len(stored) == 64


def test_five_wrong_guesses_burn_the_code(world):
    client = TestClient(world.app)
    request_code(client, BEN)
    code = last_code(world)
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        assert verify(client, BEN, wrong).status_code == 401
    assert verify(client, BEN, code).status_code == 401


def test_a_new_code_cancels_the_previous_one(world):
    client = TestClient(world.app)
    request_code(client, BEN)
    first = last_code(world)
    request_code(client, BEN)
    second = last_code(world)
    if first != second:
        assert verify(client, BEN, first).status_code == 401
    assert verify(client, BEN, second).status_code == 200


def test_expired_codes_are_rejected(world):
    client = TestClient(world.app)
    request_code(client, BEN)
    code = last_code(world)
    with system_session(world.sessions) as session:
        session.execute(update(LoginCode).values(expires_at=utcnow() - timedelta(seconds=1)))
        session.commit()
    assert verify(client, BEN, code).status_code == 401


def test_requests_are_rate_limited_per_address_without_revealing_it(world):
    client = TestClient(world.app)
    responses = [request_code(client, BEN) for _ in range(4)]
    assert {r.status_code for r in responses} == {202}
    assert len({r.text for r in responses}) == 1
    assert len(world.mailer.sent) == 3


def test_member_added_without_password_signs_in_with_a_code(world, as_user):
    anna = as_user("anna")
    email = "new.hire@musterwerk.example"
    added = anna.post(
        "/api/v1/members", json={"email": email, "display_name": "New Hire", "role": "employee"}
    )
    assert added.status_code == 201, added.text
    try:
        client = TestClient(world.app)
        password_login = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "anything-at-all"}
        )
        assert password_login.status_code == 401

        request_code(client, email)
        response = verify(client, email, last_code(world))
        assert response.status_code == 200
        assert [o["slug"] for o in response.json()["organizations"]] == ["musterwerk"]
    finally:
        anna.patch(f"/api/v1/members/{added.json()['id']}", json={"status": "revoked"})
