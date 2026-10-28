"""Guards for a public deployment: read-only demo accounts and spending limits."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from sovereign.config import Settings, is_demo_account
from sovereign.db import system_session
from sovereign.demo import PASSWORD, USERS
from sovereign.main import create_app
from sovereign.models import Message, MessageRole, utcnow


def app_with(world, **overrides):
    svc = world.app.state.services
    settings = svc.settings.model_copy(update=overrides)
    return create_app(
        settings, sessions=world.sessions, storage=svc.storage, embedder=svc.embedder,
        fake_model=world.fake, mailer=world.mailer,
    )  # fmt: skip


def sign_in(app, email: str, password: str, org_id) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    client.headers["X-Organization-Id"] = str(org_id)
    return client


def ask(client: TestClient, question: str = "What is the annual leave?"):
    conversation = client.post("/api/v1/conversations", json={}).json()["id"]
    return client.post(f"/api/v1/conversations/{conversation}/messages", json={"message": question})


def test_demo_accounts_are_recognized_only_in_demo_mode():
    on = Settings(demo_read_only=True)
    off = Settings(demo_read_only=False)
    assert is_demo_account("anna.schmidt@musterwerk.example", on)
    assert not is_demo_account("anna.schmidt@musterwerk.example", off)
    assert not is_demo_account("someone@gmail.com", on)


@pytest.fixture
def demo(world):
    app = app_with(world, demo_read_only=True)
    org = world.ids.orgs["musterwerk"]
    return app, {
        key: sign_in(app, USERS[key][0], PASSWORD, org) for key in ("anna", "ben", "clara")
    }


def test_demo_accounts_can_chat(demo):
    _, users = demo
    assert ask(users["ben"]).status_code == 200


def test_demo_accounts_cannot_change_anything(demo, world):
    app, users = demo
    anna, clara = users["anna"], users["clara"]
    handbook = world.ids.spaces["musterwerk/Company Handbook"]
    attempts = [
        anna.post("/api/v1/teams", json={"name": "Vandals"}),
        anna.post(
            "/api/v1/members",
            json={"email": "x@musterwerk.example", "display_name": "X", "password": "password123"},
        ),
        anna.patch(
            f"/api/v1/members/{world.ids.memberships[('musterwerk', 'ben')]}",
            json={"status": "revoked"},
        ),
        anna.patch(f"/api/v1/knowledge/spaces/{handbook}", json={"classification": "internal"}),
        anna.post("/api/v1/organizations", json={"name": "Spam GmbH", "slug": "spam-gmbh"}),
        clara.post(
            "/api/v1/documents",
            data={"space_id": str(handbook)},
            files={"file": ("x.md", b"# Defaced", "text/markdown")},
        ),
        clara.delete(f"/api/v1/documents/{world.ids.documents['Employee Handbook 2026']}"),
    ]
    for response in attempts:
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "demo_read_only"
    me = anna.get("/api/v1/auth/me").json()
    assert me["read_only"] is True


def test_real_accounts_keep_full_access_in_demo_mode(world, as_user):
    email = "real.admin@company.test"
    added = as_user("anna").post(
        "/api/v1/members",
        json={
            "email": email,
            "display_name": "Real",
            "role": "admin",
            "password": "real-password-1",
        },
    )
    assert added.status_code == 201, added.text
    app = app_with(world, demo_read_only=True)
    real = sign_in(app, email, "real-password-1", world.ids.orgs["musterwerk"])
    assert real.get("/api/v1/auth/me").json()["read_only"] is False
    created = real.post("/api/v1/teams", json={"name": "Real Team"})
    assert created.status_code == 201, created.text


def test_questions_per_hour_are_limited(world, as_user):
    email = "limit.tester@company.test"
    as_user("anna").post(
        "/api/v1/members",
        json={"email": email, "display_name": "Limit", "password": "limit-password-1"},
    )
    app = app_with(world, chat_messages_per_hour=2)
    client = sign_in(app, email, "limit-password-1", world.ids.orgs["musterwerk"])
    assert ask(client).status_code == 200
    assert ask(client).status_code == 200
    third = ask(client)
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"


def test_daily_limit_stops_all_model_calls(world, as_user):
    midnight = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    with system_session(world.sessions) as session:
        asked_today = session.scalar(
            select(func.count(Message.id)).where(
                Message.role == MessageRole.USER, Message.created_at >= midnight
            )
        )
    app = app_with(world, daily_message_limit=asked_today)  # already reached
    client = sign_in(app, USERS["david"][0], PASSWORD, world.ids.orgs["musterwerk"])
    calls_before = len(world.fake.calls)
    response = ask(client)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "daily_limit"
    assert len(world.fake.calls) == calls_before  # the model was never called
