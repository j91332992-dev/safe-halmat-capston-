from __future__ import annotations

from datetime import timedelta
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
import json
import re
from secrets import token_hex, token_urlsafe
from time import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field

from ..config import settings
from ..database import get_db, utcnow
from ..models.entities import AccountSiteAccess, AdminAccount, Anchor, Device, Obstacle, SiteLayout, WorkerAccount, WorkerInvite, WorkerState, Zone

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
    identity = session_identity(authorization)
    if identity.get("role") == "worker":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    site_id = identity.get("site_id")
    if not isinstance(site_id, str):
        raise HTTPException(status_code=401, detail="현장 권한을 확인할 수 없습니다.")
    return site_id


def require_worker(authorization: str | None = Header(default=None)) -> dict[str, object]:
    identity = session_identity(authorization)
    if identity.get("role") != "worker" or not identity.get("worker_id"):
        raise HTTPException(status_code=403, detail="근로자 권한이 필요합니다.")
    return identity


class WorkerAccountRequest(BaseModel):
    username: str
    password: str
    worker_id: str


class SignupRequest(BaseModel):
    username: str
    password: str
    invite_code: str


@router.post("/worker-invites/{worker_id}")
def create_worker_invite(worker_id: str, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    worker = db.get(WorkerState, worker_id)
    if not worker or worker.site_id != site_id:
        raise HTTPException(404, "해당 현장의 작업자를 찾을 수 없습니다.")
    if db.query(WorkerAccount).filter(WorkerAccount.worker_id == worker_id).first():
        raise HTTPException(409, "이미 가입된 작업자입니다.")
    code = token_urlsafe(12)
    db.add(WorkerInvite(code_hash=sha256(code.encode()).hexdigest(), worker_id=worker_id,
                        site_id=site_id, expires_at=utcnow() + timedelta(hours=24)))
    db.commit()
    return {"worker_id": worker_id, "invite_code": code, "expires_in_hours": 24}


@router.post("/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    username = _normalize_username(payload.username)
    if len(username) < 3 or len(payload.password) < 8:
        raise HTTPException(400, "ID는 3자 이상, 비밀번호는 8자 이상이어야 합니다.")
    invite = db.get(WorkerInvite, sha256(payload.invite_code.strip().encode()).hexdigest())
    if not invite or invite.used_at or invite.expires_at <= utcnow():
        raise HTTPException(400, "초대 코드가 유효하지 않거나 만료되었습니다.")
    worker = db.get(WorkerState, invite.worker_id)
    if not worker or worker.site_id != invite.site_id:
        raise HTTPException(403, "작업자 배정을 확인할 수 없습니다.")
    if db.query(AdminAccount).filter(func.upper(AdminAccount.username) == username).first() or db.query(WorkerAccount).filter(func.upper(WorkerAccount.username) == username).first():
        raise HTTPException(409, "이미 사용 중인 ID입니다.")
    if db.query(WorkerAccount).filter(WorkerAccount.worker_id == invite.worker_id).first():
        raise HTTPException(409, "이미 가입된 작업자입니다.")
    db.add(WorkerAccount(username=username, password_hash=_new_password_hash(payload.password),
                         worker_id=invite.worker_id, site_id=invite.site_id))
    invite.used_at = utcnow()
    db.commit()
    return {"username": username, "worker_id": invite.worker_id, "site_id": invite.site_id}


@router.post("/worker-accounts")
def create_worker_account(payload: WorkerAccountRequest, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    username = _normalize_username(payload.username)
    if not username or len(payload.password) < 8:
        raise HTTPException(400, "ID와 8자 이상 비밀번호가 필요합니다.")
    worker = db.get(WorkerState, payload.worker_id)
    if not worker or worker.site_id != site_id:
        raise HTTPException(404, "해당 현장의 작업자를 찾을 수 없습니다.")
    if db.query(AdminAccount).filter(func.upper(AdminAccount.username) == username).first() or db.query(WorkerAccount).filter(func.upper(WorkerAccount.username) == username).first():
        raise HTTPException(409, "이미 사용 중인 ID입니다.")
    if db.query(WorkerAccount).filter(WorkerAccount.worker_id == worker.worker_id).first():
        raise HTTPException(409, "이미 계정이 배정된 작업자입니다.")
    db.add(WorkerAccount(username=username, password_hash=_new_password_hash(payload.password), worker_id=worker.worker_id, site_id=site_id))
    db.commit()
    return {"username": username, "worker_id": worker.worker_id, "site_id": site_id}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = _normalize_username(payload.username)
    account = db.query(AdminAccount).filter(func.upper(AdminAccount.username) == username).first()
    worker_account = db.query(WorkerAccount).filter(func.upper(WorkerAccount.username) == username).first() if not account else None
    if worker_account and worker_account.active and _password_matches(payload.password, worker_account.password_hash):
        username = worker_account.username
        worker = db.get(WorkerState, worker_account.worker_id)
        if not worker or worker.site_id != worker_account.site_id:
            raise HTTPException(403, "작업자 배정을 확인할 수 없습니다.")
        token = token_urlsafe(32)
        expires_at = time() + settings.admin_session_hours * 3600
        sessions[token] = {"expires_at": expires_at, "username": username, "role": "worker", "site_id": worker_account.site_id, "worker_id": worker.worker_id}
        return {"token": token, "username": username, "role": "worker", "site_id": worker_account.site_id, "worker_id": worker.worker_id, "expires_in": settings.admin_session_hours * 3600}
    password_matches = bool(account) and _password_matches(payload.password, account.password_hash)
    if not account or not account.active or not password_matches:
        raise HTTPException(status_code=401, detail="관리자 ID 또는 비밀번호가 올바르지 않습니다.")
    username = account.username
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
    return {"username": identity["username"], "role": identity["role"], "site_id": identity["site_id"], "worker_id": identity.get("worker_id")}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    token = _token_from_header(authorization)
    if token:
        sessions.pop(token, None)
    return {"ok": True}


class RegisterRequest(BaseModel):
    username: str = Field(min_length=4, max_length=30)
    password: str = Field(min_length=4, max_length=72)
    site_name: str | None = Field(default=None, max_length=100)


def _password_digest(password: str, salt: str) -> str:
    return pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 310000
    ).hex()


def _new_password_hash(password: str) -> str:
    salt = token_hex(16)
    return f"pbkdf2_sha256${salt}${_password_digest(password, salt)}"


def _password_matches(password: str, stored_hash: str) -> bool:
    parts = stored_hash.split("$", 2)
    if len(parts) == 3 and parts[0] == "pbkdf2_sha256":
        return compare_digest(_password_digest(password, parts[1]), parts[2])
    # Compatibility with the original TUTUS/TUTUS2 fixed-salt demo accounts.
    return compare_digest(_password_digest(password, settings.admin_password_salt), stored_hash)


def _normalize_username(username: str) -> str:
    return username.strip().upper()


def _validate_username(username: str) -> None:
    if not re.fullmatch(r"[\w.-]{4,30}", username, flags=re.UNICODE):
        raise HTTPException(
            status_code=422,
            detail="아이디는 4~30자의 한글, 영문, 숫자, 밑줄(_), 마침표(.), 하이픈(-)만 사용할 수 있습니다.",
        )


def _new_session(username: str, role: str, site_id: str) -> dict[str, object]:
    token = token_urlsafe(32)
    expires_in = settings.admin_session_hours * 3600
    sessions[token] = {
        "expires_at": time() + expires_in,
        "username": username,
        "role": role,
        "site_id": site_id,
    }
    return {
        "token": token,
        "username": username,
        "role": role,
        "site_id": site_id,
        "expires_in": expires_in,
    }


@router.get("/username-available")
def username_available(username: str, db: Session = Depends(get_db)):
    normalized = _normalize_username(username)
    if len(normalized) < 4 or len(normalized) > 30 or not re.fullmatch(r"[\w.-]+", normalized, flags=re.UNICODE):
        return {"username": normalized, "available": False, "reason": "아이디 형식을 확인하세요."}
    exists = db.query(AdminAccount).filter(func.upper(AdminAccount.username) == normalized).first()
    worker_exists = db.query(WorkerAccount).filter(func.upper(WorkerAccount.username) == normalized).first()
    return {"username": normalized, "available": exists is None and worker_exists is None}


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = _normalize_username(payload.username)
    _validate_username(username)
    site_name = (payload.site_name or "").strip() or f"{username} 현장"

    duplicate = db.query(AdminAccount).filter(func.upper(AdminAccount.username) == username).first()
    if duplicate or db.query(WorkerAccount).filter(func.upper(WorkerAccount.username) == username).first():
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")

    site_id = f"site-{uuid4().hex[:10]}"
    worker_id = f"{site_id}-worker-001"
    helmet_id = f"{site_id}-helmet-001"
    role = "site_admin"
    try:
        db.add(AdminAccount(username=username, password_hash=_new_password_hash(payload.password), role=role))
        db.add(AccountSiteAccess(username=username, site_id=site_id))
        db.add(SiteLayout(site_id=site_id, name=site_name, width=10.0, height=8.0))
        db.add(
            WorkerState(
                worker_id=worker_id,
                site_id=site_id,
                worker_name=f"{site_name} 작업자",
                worker_role="general_worker",
                helmet_id=helmet_id,
                x=2.0,
                y=2.0,
                confidence=0.0,
                risk_score=0,
                risk_level="정상",
                reasons_json="[]",
                ppe_json="{}",
                hazard_json="{}",
            )
        )
        for suffix, device_type in (("av", "assistant_device"), ("uwb", "position_device")):
            db.add(
                Device(
                    device_id=f"{helmet_id}-{suffix}",
                    device_type=device_type,
                    organization_id=f"org-{site_id.removeprefix('site-')}",
                    site_id=site_id,
                    worker_id=worker_id,
                    helmet_id=helmet_id,
                    battery=None,
                    online=False,
                    component_status_json="{}",
                )
            )
        for label, x, y in (("A1", 0.0, 0.0), ("A2", 10.0, 0.0), ("A3", 0.0, 8.0), ("A4", 10.0, 8.0)):
            anchor_id = f"{site_id}-{label}"
            db.add(Anchor(anchor_id=anchor_id, site_id=site_id, name=label, x=x, y=y, z=2.2, online=False))
        db.add(
            Obstacle(
                obstacle_id=f"{site_id}-exit-main",
                site_id=site_id,
                name="주 비상구",
                object_type="emergency_exit",
                x=9.2,
                y=0.0,
                width=0.8,
                height=0.25,
            )
        )
        db.add(
            Zone(
                zone_id=f"{site_id}-zone-safety",
                site_id=site_id,
                zone_name="기본 안전관리 구역",
                zone_type="rectangle",
                zone_category="controlled",
                coordinates_json=json.dumps({"x": 6.5, "y": 5.0, "width": 2.0, "height": 1.5}),
                required_ppe_json=json.dumps(["helmet", "vest"]),
                risk_weight=20,
                warning_message="안전 장비 착용 상태를 확인하세요.",
                max_stay_seconds=0,
                active=True,
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.") from exc

    return _new_session(username, role, site_id)
