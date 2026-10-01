from __future__ import annotations

from hashlib import pbkdf2_hmac
from hmac import compare_digest
from secrets import token_urlsafe
from time import time

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
sessions: dict[str, float] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


def _hash_password(password: str) -> str:
    return pbkdf2_hmac(
        "sha256", password.encode("utf-8"), settings.admin_password_salt.encode("utf-8"), 310000
    ).hex()


def _token_from_header(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip()


def _valid_token(authorization: str | None) -> bool:
    token = _token_from_header(authorization)
    expiry = sessions.get(token or "")
    if not expiry or expiry <= time():
        if token:
            sessions.pop(token, None)
        return False
    return True


@router.post("/login")
def login(payload: LoginRequest):
    username_matches = compare_digest(payload.username.strip(), settings.admin_username)
    password_matches = compare_digest(_hash_password(payload.password), settings.admin_password_hash)
    if not (username_matches and password_matches):
        raise HTTPException(status_code=401, detail="관리자 ID 또는 비밀번호가 올바르지 않습니다.")
    token = token_urlsafe(32)
    expires_at = time() + settings.admin_session_hours * 3600
    sessions[token] = expires_at
    return {"token": token, "username": settings.admin_username, "role": "admin", "expires_in": settings.admin_session_hours * 3600}


@router.get("/session")
def session(authorization: str | None = Header(default=None)):
    if not _valid_token(authorization):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return {"username": settings.admin_username, "role": "admin"}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    token = _token_from_header(authorization)
    if token:
        sessions.pop(token, None)
    return {"ok": True}
