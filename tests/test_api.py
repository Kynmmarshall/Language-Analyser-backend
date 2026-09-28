"""API tests: auth (login/logout/csrf/origin), public analysis, and protected corpus CRUD
with revision conflicts and the public/private projection boundary.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

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


# --- Signup --------------------------------------------------------------------------------


SIGNUP_CODE = "team-code-for-tests"


@pytest.fixture
def signup_client(database: Database, settings: Settings, user: User) -> Iterator[TestClient]:
    del user
    app = create_app(
        settings=replace(settings, signup_code=SIGNUP_CODE), database=database
    )
    with TestClient(app) as test_client:
        yield test_client


def test_signup_is_disabled_by_default(client: TestClient) -> None:
    assert client.get("/api/auth/signup").json() == {"enabled": False}
    response = client.post(
        "/api/auth/signup",
        json={"username": "newbie", "password": "a-long-enough-password", "signup_code": "x"},
    )
    assert response.status_code == 403


def test_signup_reports_enabled_when_configured(signup_client: TestClient) -> None:
    assert signup_client.get("/api/auth/signup").json() == {"enabled": True}


def test_signup_creates_a_user_and_signs_them_in(signup_client: TestClient) -> None:
    response = signup_client.post(
        "/api/auth/signup",
        json={
            "username": "newbie",
            "password": "a-long-enough-password",
            "signup_code": SIGNUP_CODE,
        },
    )
    assert response.status_code == 201
    assert response.json() == {"username": "newbie"}
    assert signup_client.cookies.get("session") is not None
    assert signup_client.get("/api/auth/me").json() == {"username": "newbie"}


def test_signup_rejects_a_wrong_code(signup_client: TestClient) -> None:
    response = signup_client.post(
        "/api/auth/signup",
        json={
            "username": "newbie",
            "password": "a-long-enough-password",
            "signup_code": "not-the-code",
        },
    )
    assert response.status_code == 403
    assert signup_client.cookies.get("session") is None


def test_signup_rejects_a_duplicate_username(signup_client: TestClient) -> None:
    response = signup_client.post(
        "/api/auth/signup",
        json={
            "username": "alice",
            "password": "a-long-enough-password",
            "signup_code": SIGNUP_CODE,
        },
    )
    assert response.status_code == 409


def test_signup_enforces_password_and_username_rules(signup_client: TestClient) -> None:
    short_password = signup_client.post(
        "/api/auth/signup",
        json={"username": "newbie", "password": "short", "signup_code": SIGNUP_CODE},
    )
    assert short_password.status_code == 422

    bad_username = signup_client.post(
        "/api/auth/signup",
        json={
            "username": "has spaces",
            "password": "a-long-enough-password",
            "signup_code": SIGNUP_CODE,
        },
    )
    assert bad_username.status_code == 422


def test_signup_rejects_a_cross_origin_request(signup_client: TestClient) -> None:
    response = signup_client.post(
        "/api/auth/signup",
        json={
            "username": "newbie",
            "password": "a-long-enough-password",
            "signup_code": SIGNUP_CODE,
        },
        headers={"origin": "http://evil.example"},
    )
    assert response.status_code == 403


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


def test_accepted_statements_carry_no_suggestions(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": "Combi va au kwatt."})
    assert response.json()["suggestions"] == []


def test_a_misspelt_word_suggests_the_nearest_lexicon_entry(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": "Le resau ne passe pas."})
    body = response.json()
    assert body["parse"]["rejection_reason"] == "lexical_unknown_token"
    suggestion = body["suggestions"][0]
    assert suggestion["kind"] == "unknown_word"
    assert "resau" in suggestion["message"]
    assert "réseau" in suggestion["replacements"]
    # The span must point at the offending word so the UI can highlight it.
    text = "Le resau ne passe pas."
    assert text[suggestion["span"]["start"] : suggestion["span"]["end"]] == "resau"


def test_a_syntax_failure_reports_what_the_table_expected(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"text": "Le le le."})
    body = response.json()
    assert body["parse"]["rejection_reason"] == "syntax_no_table_entry"
    suggestion = body["suggestions"][0]
    assert suggestion["kind"] == "unexpected_token"
    assert "expected" in suggestion["message"]
    # Example words are drawn from the lexicon for whichever terminals were expected.
    assert suggestion["replacements"]


def test_an_accented_twin_is_offered_when_the_plain_spelling_blocks_the_parse(
    client: TestClient,
) -> None:
    # 'la' and 'là' are different words, so the lexer takes the spelling as written; the
    # suggester is what points out the other reading.
    response = client.post("/api/analyze", json={"text": "la nga la es ma combi"})
    body = response.json()
    assert body["parse"]["accepted"] is False
    messages = [s["message"] for s in body["suggestions"]]
    assert any("'là'" in message for message in messages)
    # Reported once, however many times the word occurs.
    assert sum("was read as DET" in message for message in messages) == 1

    accepted = client.post("/api/analyze", json={"text": "la nga là es ma combi"})
    assert accepted.json()["parse"]["accepted"] is True


def test_suggestions_are_identical_across_runs(client: TestClient) -> None:
    payload = {"text": "Le resau ne passe pas."}
    first = client.post("/api/analyze", json=payload).json()["suggestions"]
    second = client.post("/api/analyze", json=payload).json()["suggestions"]
    assert first == second


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


# --- Public grammar --------------------------------------------------------------------


def test_grammar_is_public_and_reports_a_conflict_free_ll1_table(client: TestClient) -> None:
    response = client.get("/api/grammar")
    assert response.status_code == 200
    body = response.json()
    assert len(body["lexicon"]) > 0
    assert len(body["transformation_steps"]) > 0
    assert body["table_conflicts"] == []
    assert len(body["table_entries"]) > 0
    assert len(body["first"]) > 0
    assert len(body["follow"]) > 0


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
            "manual_transcription_attested": False, "topics": [],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 409


def test_statement_id_and_collector_are_assigned_when_omitted(client: TestClient) -> None:
    login(client)
    response = client.post(
        "/api/corpus",
        json={
            "source_kind": "field", "raw_text": "Le taximan waka.",
            "manual_transcription_attested": True, "topics": [],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["statement_id"] == "field-001"
    assert body["collector_id"] == "alice"


def test_generated_statement_ids_increment_per_source_kind(client: TestClient) -> None:
    login(client)

    def create(source_kind: str) -> str:
        response = client.post(
            "/api/corpus",
            json={
                "source_kind": source_kind, "raw_text": "Combi va au kwatt.",
                "manual_transcription_attested": source_kind == "field", "topics": [],
            },
            headers=csrf_headers(client),
        )
        assert response.status_code == 201
        return response.json()["statement_id"]

    assert create("field") == "field-001"
    assert create("field") == "field-002"
    assert create("demo") == "demo-001"


def test_collector_id_cannot_be_spoofed_on_create(client: TestClient) -> None:
    login(client)
    response = client.post(
        "/api/corpus",
        json={
            "source_kind": "field", "raw_text": "Le taximan waka.",
            "manual_transcription_attested": True, "collector_id": "somebody-else",
            "topics": [],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    assert response.json()["collector_id"] == "alice"


def test_editing_keeps_the_original_collector_when_omitted(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    response = client.patch(
        "/api/corpus/s-001",
        json={
            "expected_revision": 1, "raw_text": "Le taximan waka.", "source_kind": "field",
            "manual_transcription_attested": True, "topics": [],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["collector_id"] == "alice"


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


# --- Statistics ----------------------------------------------------------------------------


def test_statistics_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/statistics").status_code == 401


def test_statistics_reflects_the_current_corpus(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    response = client.get("/api/statistics", headers=csrf_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["statement_count"] == 1
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 0
    assert body["skipped_invalid_count"] == 0
    assert {"term": "commuting", "count": 1} in body["topic_counts"]
    assert body["unknown_words"] == []
    assert any(item["term"] == "combi" for item in body["canonical_frequency"])


def test_statistics_reports_unknown_words_without_crashing(client: TestClient) -> None:
    login(client)
    client.post(
        "/api/corpus",
        json={
            "statement_id": "s-002", "source_kind": "demo", "raw_text": "Blorptastic zibble.",
            "manual_transcription_attested": False, "collector_id": "alice", "topics": [],
        },
        headers=csrf_headers(client),
    )
    response = client.get("/api/statistics", headers=csrf_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["rejected_count"] == 1
    assert set(body["unknown_words"]) == {"Blorptastic", "zibble"}


# --- Evidence export -------------------------------------------------------------------


def test_export_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/export").status_code == 401
    assert client.get("/api/export/csv").status_code == 401


def test_export_all_scope_includes_full_metadata(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    response = client.get("/api/export", headers=csrf_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "all"
    assert len(body["statements"]) == 1
    statement = body["statements"][0]
    assert statement["collector_id"] == "alice"
    assert statement["published"] is False
    assert len(body["results"]) == 1
    assert len(body["lexicon"]) > 0


def test_export_published_scope_redacts_and_filters(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    response = client.get("/api/export?scope=published", headers=csrf_headers(client))
    assert response.json()["statements"] == []

    client.post("/api/corpus/s-001/publish", json={"revision": 1}, headers=csrf_headers(client))
    response = client.get("/api/export?scope=published", headers=csrf_headers(client))
    body = response.json()
    assert len(body["statements"]) == 1
    statement = body["statements"][0]
    assert statement["collector_id"] is None
    assert statement["manual_transcription_attested"] is None
    assert statement["published"] is True


def test_export_csv_is_downloadable(client: TestClient) -> None:
    login(client)
    _create_statement(client)
    response = client.get("/api/export/csv", headers=csrf_headers(client))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("statement_id,revision,source_kind")
    assert "s-001" in lines[1]


# --- Health ------------------------------------------------------------------------------


def test_health_endpoints_report_ready(client: TestClient) -> None:
    assert client.get("/api/health/live").json() == {"status": "ok"}
    assert client.get("/api/health/ready").json() == {"status": "ok"}
