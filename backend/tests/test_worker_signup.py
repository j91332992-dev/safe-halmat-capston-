import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.entities import WorkerState
from app.routers.auth import LoginRequest, SignupRequest, create_worker_invite, login, signup


def test_worker_signup_requires_single_use_invite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(WorkerState(worker_id="worker-test", site_id="site-001", worker_name="테스트 근로자", helmet_id="helmet-test"))
        db.commit()

        invitation = create_worker_invite("worker-test", site_id="site-001", db=db)
        account = signup(SignupRequest(username="worker-test-login", password="secure-pass-123", invite_code=invitation["invite_code"]), db=db)
        assert account["worker_id"] == "worker-test"
        session = login(LoginRequest(username="worker-test-login", password="secure-pass-123"), db=db)
        assert session["role"] == "worker"
        assert session["worker_id"] == "worker-test"

        with pytest.raises(HTTPException) as error:
            signup(SignupRequest(username="second-login", password="secure-pass-123", invite_code=invitation["invite_code"]), db=db)
        assert error.value.status_code == 400

        with pytest.raises(HTTPException) as error:
            create_worker_invite("worker-test", site_id="site-002", db=db)
        assert error.value.status_code == 404
