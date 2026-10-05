from __future__ import annotations

from hashlib import pbkdf2_hmac
from hmac import compare_digest
from secrets import token_urlsafe
from time import time

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..config import settings
from ..database import get_db
from ..models.entities import AccountSiteAccess, AdminAccount

router = APIRouter(prefix="/api/auth", tags=["auth"])
sessions: dict[str, dict[str, object]] = {}


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


def session_identity(authorization: str | None) -> dict[str, object]:
    token = _token_from_header(authorization)
    identity = sessions.get(token or "")
    expiry = identity.get("expires_at") if identity else None
    if not identity or not isinstance(expiry, float) or expiry <= time():
        if token:
            sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return identity


def require_site(authorization: str | None = Header(default=None)) -> str:
    site_id = session_identity(authorization).get("site_id")
    if not isinstance(site_id, str):
        raise HTTPException(status_code=401, detail="현장 권한을 확인할 수 없습니다.")
    return site_id


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    account = db.get(AdminAccount, username)
    password_matches = bool(account) and compare_digest(_hash_password(payload.password), account.password_hash)
    if not account or not account.active or not password_matches:
        raise HTTPException(status_code=401, detail="관리자 ID 또는 비밀번호가 올바르지 않습니다.")
    access = db.query(AccountSiteAccess).filter(AccountSiteAccess.username == username).order_by(AccountSiteAccess.site_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="배정된 현장이 없는 관리자 계정입니다.")
    token = token_urlsafe(32)
    expires_at = time() + settings.admin_session_hours * 3600
    sessions[token] = {"expires_at": expires_at, "username": username, "role": account.role, "site_id": access.site_id}
    return {"token": token, "username": username, "role": account.role, "site_id": access.site_id, "expires_in": settings.admin_session_hours * 3600}


@router.get("/session")
def session(authorization: str | None = Header(default=None)):
    identity = session_identity(authorization)
    return {"username": identity["username"], "role": identity["role"], "site_id": identity["site_id"]}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    token = _token_from_header(authorization)
    if token:
        sessions.pop(token, None)
    return {"ok": True}
