"""Persistence layer: SQLAlchemy models (models.py) and the Database/session wrapper (db.py).

An app or test constructs exactly one `Database` and threads it through the app instead
of relying on module-level global engine state, so tests can use an isolated database.
"""
