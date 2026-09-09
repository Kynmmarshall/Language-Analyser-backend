"""FastAPI application factory.

No module-level app instance here (importing this module must have no side effects,
so tests can safely `from yaounde_analyzer.api.main import create_app` and build their
own isolated app/database). See asgi.py for the actual runnable `app` object.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from yaounde_analyzer.api.routes import analysis as analysis_routes
from yaounde_analyzer.api.routes import auth as auth_routes
from yaounde_analyzer.api.routes import corpus as corpus_routes
from yaounde_analyzer.api.routes import grammar as grammar_routes
from yaounde_analyzer.api.routes import statistics as statistics_routes
from yaounde_analyzer.api.settings import Settings
from yaounde_analyzer.core.analysis import PreparedAnalyzer
from yaounde_analyzer.core.specs import load_demo_grammar, load_demo_lexicon
from yaounde_analyzer.storage.db import Database


def create_app(*, settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    database = database or Database.create(settings.database_url)
    database.init_schema()

    # Grammar validity is checked once here, before the app serves any traffic.
    analyzer = PreparedAnalyzer(load_demo_lexicon(), load_demo_grammar())
    analyzer.check()

    app = FastAPI(title="Francanglais Studio API")
    app.state.settings = settings
    app.state.db = database
    app.state.analyzer = analyzer

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["content-type", "x-csrf-token"],
    )

    app.include_router(auth_routes.router)
    app.include_router(analysis_routes.router)
    app.include_router(corpus_routes.router)
    app.include_router(grammar_routes.router)
    app.include_router(statistics_routes.router)

    @app.get("/api/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health/ready")
    def ready() -> dict[str, str]:
        return {"status": "ok" if app.state.analyzer.table.is_ll1 else "degraded"}

    return app
