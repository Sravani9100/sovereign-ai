import json
import os
import re
from dataclasses import dataclass

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from sovereign.ai.embeddings import HashingEmbedder
from sovereign.ai.gateway import FakeChatModel
from sovereign.config import Settings
from sovereign.db import make_engine, make_sessionmaker, system_session
from sovereign.demo import PASSWORD, USERS, DemoIds, reset, seed
from sovereign.main import create_app
from sovereign.models import Classification, ModelProfile, Provider
from sovereign.storage import LocalStorage


def _test_database_url() -> str | None:
    """From the environment or .env. Tests wipe this database, so it's never the app's."""
    if url := os.environ.get("SOVEREIGN_TEST_DATABASE_URL"):
        return url
    for path in (".env", "../.env"):
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig") as env:
                for line in env:
                    key, _, value = line.strip().partition("=")
                    if key == "SOVEREIGN_TEST_DATABASE_URL" and value:
                        return value
    return None


@dataclass
class World:
    app: object
    ids: DemoIds
    fake: FakeChatModel
    sessions: object


@pytest.fixture(scope="session")
def world(tmp_path_factory) -> World:
    url = _test_database_url()
    if url is None:
        pytest.skip("SOVEREIGN_TEST_DATABASE_URL is not set")
    config = Config("alembic.ini")
    config.attributes["database_url"] = url
    command.upgrade(config, "head")

    settings = Settings(
        database_url=url,
        jwt_secret="test-secret-that-is-long-enough-for-hs256-signing",
        storage_dir=tmp_path_factory.mktemp("storage"),
        inline_ingestion=True,
        # The hashing embedder isn't semantic: keep every permitted candidate so the
        # isolation tests see the widest possible retrieval.
        min_similarity=-1.0,
        retrieval_k=50,
        retrieval_candidates=50,
    )
    sessions = make_sessionmaker(make_engine(url))
    storage = LocalStorage(settings.storage_dir)
    embedder = HashingEmbedder()
    reset(sessions)
    ids = seed(sessions, settings, storage, embedder)

    # Test-only model profiles: one capped at internal data, one allowed confidential data.
    with system_session(sessions) as session:
        session.query(ModelProfile).update({"enabled": False, "is_default": False})
        for org_id in ids.orgs.values():
            session.add_all(
                [
                    ModelProfile(
                        organization_id=org_id,
                        name="test-external",
                        provider=Provider.FAKE,
                        model="fake",
                        max_classification=Classification.INTERNAL,
                        is_default=True,
                    ),
                    ModelProfile(
                        organization_id=org_id,
                        name="test-local",
                        provider=Provider.FAKE,
                        model="fake",
                        max_classification=Classification.CONFIDENTIAL,
                    ),
                ]
            )
        session.commit()

    fake = FakeChatModel(respond=lambda system, messages: "Here is what I found [1].")
    app = create_app(settings, sessions=sessions, storage=storage, embedder=embedder,
                     fake_model=fake)  # fmt: skip
    return World(app=app, ids=ids, fake=fake, sessions=sessions)


class UserClient:
    def __init__(self, world: World, user: str, org: str) -> None:
        self.world = world
        self.client = TestClient(world.app)
        response = self.client.post(
            "/api/v1/auth/login", json={"email": USERS[user][0], "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        self.org_id = world.ids.orgs[org]
        self.client.headers["X-Organization-Id"] = str(self.org_id)

    def get(self, url, **kwargs):
        return self.client.get(url, **kwargs)

    def post(self, url, **kwargs):
        return self.client.post(url, **kwargs)

    def patch(self, url, **kwargs):
        return self.client.patch(url, **kwargs)

    def put(self, url, **kwargs):
        return self.client.put(url, **kwargs)

    def delete(self, url, **kwargs):
        return self.client.delete(url, **kwargs)

    def ask(self, question: str, **body) -> "Answer":
        conversation = self.post("/api/v1/conversations", json={}).json()["id"]
        calls_before = len(self.world.fake.calls)
        response = self.post(
            f"/api/v1/conversations/{conversation}/messages", json={"message": question, **body}
        )
        assert response.status_code == 200, response.text
        events = parse_sse(response.text)
        new_calls = self.world.fake.calls[calls_before:]
        model_input = json.dumps(new_calls[-1]) if new_calls else ""
        return Answer(conversation, events, model_input)


@dataclass
class Answer:
    conversation_id: str
    events: list[tuple[str, dict]]
    model_input: str  # everything the model was shown, as one string

    @property
    def done(self) -> dict:
        return next(data for event, data in self.events if event == "done")

    @property
    def source_count(self) -> int:
        return next(data for event, data in self.events if event == "sources")["count"]


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        match = re.match(r"event: (\w+)\ndata: (.*)", block, re.S)
        if match:
            events.append((match.group(1), json.loads(match.group(2))))
    return events


@pytest.fixture
def as_user(world):
    return lambda user, org="musterwerk": UserClient(world, user, org)
