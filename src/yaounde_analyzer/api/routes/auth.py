"""Login/logout/me endpoints: database-backed sessions, HttpOnly cookie, CSRF token issue."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from yaounde_analyzer.api.deps import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    get_db,
    get_settings,
    require_csrf,
    require_same_origin,
    require_user,
)
from yaounde_analyzer.api.repository import (
    authenticate_user,
    create_auth_session,
    revoke_auth_session,
)
from yaounde_analyzer.api.schemas import LoginRequest, UserPublic
from yaounde_analyzer.api.settings import Settings
from yaounde_analyzer.storage.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookies(
    response: Response, settings: Settings, raw_token: str, csrf_token: str
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME, value=raw_token, httponly=True, secure=settings.cookie_secure,
        samesite="lax", max_age=settings.session_lifetime_seconds, path="/",
    )
    # Readable by the frontend so it can echo it back as the CSRF header (double-submit).
    response.set_cookie(
        key=CSRF_COOKIE_NAME, value=csrf_token, httponly=False, secure=settings.cookie_secure,
        samesite="lax", max_age=settings.session_lifetime_seconds, path="/",
    )


@router.post("/login", response_model=UserPublic, dependencies=[Depends(require_same_origin)])
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserPublic:
    user = authenticate_user(session, payload.username, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    _, raw_token, csrf_token = create_auth_session(session, user, settings.session_lifetime_seconds)
    _set_session_cookies(response, settings, raw_token, csrf_token)
    return UserPublic(username=user.username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: Session = Depends(get_db),
    _user: User = Depends(require_csrf),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> None:
    if session_token:
        revoke_auth_session(session, session_token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(require_user)) -> UserPublic:
    return UserPublic(username=user.username)


__all__ = ["router", "CSRF_HEADER_NAME"]
