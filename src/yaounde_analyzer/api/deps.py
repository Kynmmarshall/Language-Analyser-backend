"""FastAPI dependencies: database session, current user, and CSRF/Origin protection."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from yaounde_analyzer.api.repository import get_valid_auth_session
from yaounde_analyzer.api.security import constant_time_equals
from yaounde_analyzer.api.settings import Settings
from yaounde_analyzer.core.analysis import PreparedAnalyzer
from yaounde_analyzer.storage.models import AuthSession, User

SESSION_COOKIE_NAME = "session"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_COOKIE_NAME = "csrf_token"


def get_db(request: Request) -> Generator[Session]:
    yield from request.app.state.db.session_scope()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_analyzer(request: Request) -> PreparedAnalyzer:
    return request.app.state.analyzer


def get_optional_auth_session(
    session: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> AuthSession | None:
    if session_token is None:
        return None
    return get_valid_auth_session(session, session_token)


def require_user(
    auth_session: AuthSession | None = Depends(get_optional_auth_session),
) -> User:
    if auth_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return auth_session.user


def require_csrf(
    auth_session: AuthSession | None = Depends(get_optional_auth_session),
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER_NAME),
) -> User:
    """Require a valid session AND a matching double-submit CSRF header, for any
    state-changing request made with the session cookie (all protected writes)."""
    if auth_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if csrf_header is None or not constant_time_equals(csrf_header, auth_session.csrf_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing or invalid CSRF token")
    return auth_session.user


def require_same_origin(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """Reject cross-origin state-changing requests that predate a session (e.g. login).

    Trusts the request's own origin (same-origin deployment, per Phase 4) as well as any
    configured frontend origin (separate dev servers for the SPA and API)."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    self_origin = f"{request.url.scheme}://{request.url.netloc}"
    if origin != self_origin and origin not in settings.cors_origins:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cross-origin request rejected")
