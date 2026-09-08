"""ASGI entry point: `uvicorn yaounde_analyzer.api.asgi:app`."""

from __future__ import annotations

from yaounde_analyzer.api.main import create_app

app = create_app()
