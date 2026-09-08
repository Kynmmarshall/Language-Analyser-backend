"""API tests: auth (login/logout/csrf/origin), public analysis, and protected corpus CRUD
with revision conflicts and the public/private projection boundary.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from yaounde_analyzer.api.main import create_app
from yaounde_analyzer.api.repository import create_user
from yaounde_analyzer.api.settings import Settings
from yaounde_analyzer.storage.db import Database
from yaounde_analyzer.storage.models import User

PASSWORD = "correct horse battery staple"


@pytest.fixture
def database() -> Database:
    db = Database.create("sqlite:///:memory:")
    db.init_schema()
    return db


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:", cookie_secure=False,
        session_lifetime_seconds=3600, max_anonymous_text_characters=2000,
    )


@pytest.fixture
def user(database: Database) -> User:
    session = database.session_factory()
    try:
        return create_user(session, "alice", PASSWORD)
    finally:
        session.close()


@pytest.fixture
def client(database: Database, settings: Settings, user: User) -> Iterator[TestClient]:
    del user  # ensures the user fixture runs (and is created) before the app/client exist
    app = create_app(settings=settings, database=database)
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username: str = "alice", password: str = PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    assert token is not None
    return {"x-csrf-token": token}


# --- Auth ----------------------------------------------------------------------------------


def test_login_success_sets_cookies_and_returns_username(client: TestClient) -> None:
    response = login(client)
    assert response.status_code == 200
    assert response.json() == {"username": "alice"}
    assert client.cookies.get("session") is not None
    assert client.cookies.get("csrf_token") is not None


def test_login_wrong_password_is_rejected(client: TestClient) -> None:
    response = login(client, password="wrong password")
    assert response.status_code == 401
    assert client.cookies.get("session") is None


def test_login_rejects_a_mismatched_cross_origin_request(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": PASSWORD},
        headers={"origin": "http://evil.example"},
    )
    assert response.status_code == 403


def test_me_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_username_after_login(client: TestClient) -> None:
    login(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"username": "alice"}


def test_logout_requires_csrf_token(client: TestClient) -> None:
    login(client)
    assert client.post("/api/auth/logout").status_code == 403


def test_logout_revokes_the_session(client: TestClient) -> None:
    login(client)
    response = client.post("/api/auth/logout", headers=csrf_headers(client))
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


# --- Public analysis -------------------------------------------------------------------


def test_public_analyze_accepts_a_constructed_sentence(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": "Combi va au kwatt."})
    assert response.status_code == 200
    body = response.json()
    assert body["parse"]["accepted"] is True


def test_public_analyze_reports_unknown_vocabulary(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": "On go au marché."})
    assert response.status_code == 200
    assert response.json()["parse"]["rejection_reason"] == "lexical_unknown_token"


def test_public_analyze_rejects_blank_and_oversized_text(client: TestClient) -> None:
    assert client.post("/api/analyze", json={"text": "   "}).status_code == 422
    assert client.post("/api/analyze", json={"text": "x" * 2001}).status_code == 422


def test_public_analyze_rejects_a_different_target_variety(client: TestClient) -> None:
    response = client.post(
        "/api/analyze", json={"text": "hello", "target_variety": "english"}
    )
    assert response.status_code == 422


def test_analyze_never_persists_anything(client: TestClient) -> None:
    login(client)
    client.post("/api/analyze", json={"text": "Combi va au kwatt."})
    corpus = client.get("/api/corpus", headers=csrf_headers(client)).json()
    assert corpus == []


# --- Corpus: authorization ---------------------------------------------------------------


def test_corpus_list_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/corpus").status_code == 401


def test_corpus_create_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/corpus",
        json={
            "statement_id": "s-001", "source_kind": "demo", "raw_text": "Combi va au kwatt.",
            "manual_transcription_attested": False, "collector_id": "test", "topics": [],
        },
    )
    assert response.status_code == 401


def test_corpus_create_requires_csrf_token_even_when_logged_in(client: TestClient) -> None:
    login(client)
    response = client.post(
        "/api/corpus",
        json={
            "statement_id": "s-001", "source_kind": "demo", "raw_text": "Combi va au kwatt.",
            "manual_transcription_attested": False, "collector_id": "test", "topics": [],
        },
    )
    assert response.status_code == 403


# --- Corpus: CRUD, revisions, and publication ------------------------------------------


def _create_statement(client: TestClient, statement_id: str = "s-001") -> dict:
    response = client.post(
        "/api/corpus",
        json={
            "statement_id": statement_id, "source_kind": "demo",
            "raw_text": "Combi va au kwatt.",
            "manual_transcription_attested": False, "collector_id": "alice",
            "topics": ["commuting"],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_read_a_corpus_statement(client: TestClient) -> None:
    login(client)
    created = _create_statement(client)
    assert created["revision"] == 1
    assert created["published_revision"] is None

    fetched = client.get("/api/corpus/s-001", headers=csrf_headers(client)).json()
    assert fetched == created


def test_creating_a_duplicate_statement_id_is_rejected(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    response = client.post(
        "/api/corpus",
        json={
            "statement_id": "s-001", "source_kind": "demo", "raw_text": "Autre texte.",
            "manual_transcription_attested": False, "collector_id": "alice", "topics": [],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 409


def test_updating_with_the_correct_expected_revision_succeeds(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    response = client.patch(
        "/api/corpus/s-001",
        json={
            "expected_revision": 1, "raw_text": "Le taximan waka.", "source_kind": "field",
            "manual_transcription_attested": True, "collector_id": "alice", "topics": ["commuting"],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 2
    assert body["raw_text"] == "Le taximan waka."


def test_updating_with_a_stale_expected_revision_returns_409(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    client.patch(
        "/api/corpus/s-001",
        json={
            "expected_revision": 1, "raw_text": "Le taximan waka.", "source_kind": "field",
            "manual_transcription_attested": True, "collector_id": "alice", "topics": [],
        },
        headers=csrf_headers(client),
    )
    stale = client.patch(
        "/api/corpus/s-001",
        json={
            "expected_revision": 1, "raw_text": "Un autre texte.", "source_kind": "field",
            "manual_transcription_attested": True, "collector_id": "alice", "topics": [],
        },
        headers=csrf_headers(client),
    )
    assert stale.status_code == 409


def test_history_lists_every_revision_in_order(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    client.patch(
        "/api/corpus/s-001",
        json={
            "expected_revision": 1, "raw_text": "Le taximan waka.", "source_kind": "field",
            "manual_transcription_attested": True, "collector_id": "alice", "topics": [],
        },
        headers=csrf_headers(client),
    )
    history = client.get("/api/corpus/s-001/history", headers=csrf_headers(client)).json()
    assert [h["revision"] for h in history] == [1, 2]
    assert history[0]["created_by"] == "alice"


def test_publishing_makes_a_statement_appear_in_public_examples(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    assert client.get("/api/examples").json() == []

    response = client.post(
        "/api/corpus/s-001/publish", json={"revision": 1}, headers=csrf_headers(client)
    )
    assert response.status_code == 200
    assert response.json()["published_revision"] == 1

    examples = client.get("/api/examples").json()
    assert examples == [
        {"statement_id": "s-001", "raw_text": "Combi va au kwatt.", "topics": ["commuting"]}
    ]


def test_public_examples_never_expose_private_fields(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    client.post("/api/corpus/s-001/publish", json={"revision": 1}, headers=csrf_headers(client))
    example = client.get("/api/examples").json()[0]
    assert set(example.keys()) == {"statement_id", "raw_text", "topics"}


def test_editing_a_published_statement_unpublishes_it(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    client.post("/api/corpus/s-001/publish", json={"revision": 1}, headers=csrf_headers(client))
    assert len(client.get("/api/examples").json()) == 1

    client.patch(
        "/api/corpus/s-001",
        json={
            "expected_revision": 1, "raw_text": "Nouveau texte.", "source_kind": "field",
            "manual_transcription_attested": True, "collector_id": "alice", "topics": [],
        },
        headers=csrf_headers(client),
    )
    assert client.get("/api/examples").json() == []
    private = client.get("/api/corpus/s-001", headers=csrf_headers(client)).json()
    assert private["published_revision"] is None


def test_unpublish_removes_a_statement_from_public_examples(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    client.post("/api/corpus/s-001/publish", json={"revision": 1}, headers=csrf_headers(client))
    client.post("/api/corpus/s-001/unpublish", headers=csrf_headers(client))
    assert client.get("/api/examples").json() == []


def test_operating_on_an_unknown_statement_returns_404(client: TestClient) -> None:
    login(client)
    assert client.get("/api/corpus/missing", headers=csrf_headers(client)).status_code == 404


# --- Health ------------------------------------------------------------------------------


def test_health_endpoints_report_ready(client: TestClient) -> None:
    assert client.get("/api/health/live").json() == {"status": "ok"}
    assert client.get("/api/health/ready").json() == {"status": "ok"}
