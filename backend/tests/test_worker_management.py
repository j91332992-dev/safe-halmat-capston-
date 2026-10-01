from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.entities import WorkerState
from app.routers.workers import router


def test_worker_name_and_notes_can_be_updated():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with session_factory() as db:
        db.add(WorkerState(worker_id="worker-test", worker_name="기존 이름", notes="", helmet_id="helmet-test"))
        db.commit()

    test_app = FastAPI()
    test_app.include_router(router)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_db
    with TestClient(test_app) as client:
        response = client.put("/api/workers/worker-test", json={"worker_name": "김작업", "notes": "고소 작업 교육 이수"})
        assert response.status_code == 200
        assert response.json()["worker_name"] == "김작업"
        assert response.json()["notes"] == "고소 작업 교육 이수"
