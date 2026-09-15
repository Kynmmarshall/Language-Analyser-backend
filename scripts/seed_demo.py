"""Idempotent loader for the demo corpus fixture in data/demo.json.

The fixture on its own is only a test artifact: /api/examples reads the database, so
without this script the demo statements never reach the running app. Each statement is
created and published once; re-running skips anything already present.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from yaounde_analyzer.api.repository import (
    create_statement,
    create_user,
    get_statement_record,
    get_user_by_username,
    publish_revision,
)
from yaounde_analyzer.api.settings import Settings
from yaounde_analyzer.core.corpus import validate_import
from yaounde_analyzer.storage.db import Database

DEMO_CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "demo.json"
DEMO_USERNAME = "demo_fixture"


def main() -> None:
    settings = Settings.from_env()
    database = Database.create(settings.database_url)
    database.init_schema()
    session = database.session_factory()
    try:
        user = get_user_by_username(session, DEMO_USERNAME)
        if user is None:
            # This account only exists to own the fixture rows, which the schema requires.
            # The password is random and discarded so the account cannot be signed into.
            user = create_user(session, DEMO_USERNAME, secrets.token_urlsafe(32))
            print(f"Seeded user {DEMO_USERNAME!r}.")

        revisions = validate_import(json.loads(DEMO_CORPUS_PATH.read_text(encoding="utf-8")))
        created = 0
        for revision in revisions:
            if get_statement_record(session, revision.statement_id) is not None:
                continue
            create_statement(
                session,
                statement_id=revision.statement_id,
                source_kind=revision.source_kind,
                raw_text=revision.raw_text,
                manual_transcription_attested=revision.manual_transcription_attested,
                collector_id=revision.collector_id,
                topics=revision.topics,
                created_by_user_id=user.id,
            )
            publish_revision(session, revision.statement_id, 1)
            created += 1
        print(f"Seeded and published {created} demo statement(s); {len(revisions)} in fixture.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
