"""Idempotent test-data seed for local Playwright e2e runs. Not for production use.

Safe to run repeatedly: creates the fixed e2e collector account and one seed statement
only if they do not already exist, against a dedicated e2e-only SQLite database.
"""

from __future__ import annotations

from yaounde_analyzer.api.repository import (
    create_statement,
    create_user,
    get_statement_record,
    get_user_by_username,
)
from yaounde_analyzer.api.settings import Settings
from yaounde_analyzer.storage.db import Database

E2E_USERNAME = "e2e_collector"
E2E_PASSWORD = "e2e-local-test-fixture-only"  # not a real credential; local test use only
E2E_STATEMENT_ID = "e2e-seed-001"


def main() -> None:
    settings = Settings.from_env()
    database = Database.create(settings.database_url)
    database.init_schema()
    session = database.session_factory()
    try:
        user = get_user_by_username(session, E2E_USERNAME)
        if user is None:
            user = create_user(session, E2E_USERNAME, E2E_PASSWORD)
            print(f"Seeded user {E2E_USERNAME!r}.")

        if get_statement_record(session, E2E_STATEMENT_ID) is None:
            create_statement(
                session,
                statement_id=E2E_STATEMENT_ID,
                source_kind="demo",
                raw_text="Combi va au kwatt.",
                manual_transcription_attested=False,
                collector_id=E2E_USERNAME,
                topics=("commuting",),
                created_by_user_id=user.id,
            )
            print(f"Seeded statement {E2E_STATEMENT_ID!r}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
