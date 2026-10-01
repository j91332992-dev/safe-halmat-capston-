from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.entities import Anchor, SiteLayout
from app.routers.layout import router


def test_draft_is_saved_before_it_is_applied():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with testing_session() as db:
        db.add(SiteLayout(site_id="site-001", name="기존 작업장", width=5.8, height=8.2))
        db.add(Anchor(anchor_id="anchor-001", name="A1", x=0, y=0, z=2.2, online=True))
        db.commit()

    test_app = FastAPI()
    test_app.include_router(router)

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_db
    draft = {
        "site": {"name": "새 설계안", "width": 10, "height": 12},
        "anchors": [{"anchor_id": "anchor-001", "name": "A1", "x": 1, "y": 2, "z": 2.5, "online": True}],
        "obstacles": [{"obstacle_id": "wall-1", "name": "가설 벽", "x": 2, "y": 3, "width": 1, "height": 4}],
        "zones": [{
            "zone_id": "restricted-1",
            "zone_name": "관리자 전용",
            "zone_type": "rectangle",
            "coordinates": {"x": 4, "y": 4, "width": 2, "height": 2},
            "required_ppe": [],
            "allowed_worker_ids": ["worker-001"],
            "risk_weight": 30,
            "warning_message": "출입 제한",
            "max_stay_seconds": 0,
            "active": True
        }]
    }

    with TestClient(test_app) as client:
        assert client.put("/api/layout/draft", json=draft).status_code == 200
        version = client.post("/api/layout/versions", json={"name": "첫 설계"})
        assert version.status_code == 200
        assert client.get("/api/layout/versions").json()[0]["name"] == "첫 설계"
        assert client.get("/api/layout").json()["site"]["name"] == "기존 작업장"
        assert client.post("/api/layout/apply").status_code == 200
        actual = client.get("/api/layout").json()
        assert actual["site"]["name"] == "새 설계안"
        assert actual["obstacles"][0]["name"] == "가설 벽"
        assert actual["zones"][0]["allowed_worker_ids"] == ["worker-001"]
