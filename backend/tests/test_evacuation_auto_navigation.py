import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base
from app.models.entities import WorkerState, SiteLayout, Obstacle, EvacuationNavigationPolicy
from app.services.evacuation_service import trigger_fire, calculate_route
from app.services.evacuation_navigation import map_signature

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(SiteLayout(site_id="s", width=5.6, height=3.7))
        session.add(WorkerState(worker_id="w", site_id="s", helmet_id="h", x=.5, y=.5))
        session.add(Obstacle(obstacle_id="exit",site_id="s",name="exit",object_type="emergency_exit",x=5.2,y=3.3,width=.4,height=.4))
        session.add(Obstacle(obstacle_id="table",site_id="s",name="table",object_type="obstacle",x=1.6,y=1.25,width=2.4,height=1.2))
        session.commit()
        yield session

@pytest.mark.parametrize("verified", [True, False])
def test_auto_requires_unchanged_map(db, verified):
    db.add(EvacuationNavigationPolicy(site_id="s",enabled=True,map_signature=map_signature(db,"s") if verified else "outdated"))
    db.flush()
    incident, created=trigger_fire(db,"manager","w",{"drill":True,"navigation_enabled":True})
    assert created
    assert bool(json.loads(incident.details_json).get("navigation_enabled")) == verified

def test_route_avoids_table(db):
    result=calculate_route(db,db.get(WorkerState,"w"))
    assert result["available"] and len(result["path"]) > 2
    from app.services.evacuation_service import _blocked
    objects=db.query(Obstacle).all()
    for a,b in zip(result["path"],result["path"][1:]):
        for i in range(101):
            t=i/100
            assert not _blocked(a["x"]+(b["x"]-a["x"])*t,a["y"]+(b["y"]-a["y"])*t,objects,None)


@pytest.mark.parametrize("x,history,allowed", [(1.45,[],True),(1.8,[(1.2,1.8)],True),(1.8,[],False),(2.0,[(1.2,1.8)],False)])
def test_boundary_start(db,x,history,allowed):
    from app.services.route_start_service import corrected_start
    from app.services.evacuation_service import _blocked
    objects=db.query(Obstacle).all()
    cell,info=corrected_start(x,1.8,objects,5.6,3.7,.2,.25,lambda a,b:_blocked(a,b,objects,None),history)
    assert bool(cell) == allowed
    if cell:
        assert cell[0]*.2 < 1.6-.25
        assert not _blocked(cell[0]*.2,cell[1]*.2,objects,None)
        assert info["applied"] and info["distance_m"] <= .8

def test_boundary_route_avoids_table(db):
    w=db.get(WorkerState,"w");w.x=1.45;w.y=1.8
    result=calculate_route(db,w)
    assert result["available"] and result["start_correction"]["applied"]
    assert w.x==1.45
    from app.services.evacuation_service import _blocked
    objects=db.query(Obstacle).all()
    for a,b in zip(result["path"],result["path"][1:]):
        for i in range(101):
            t=i/100
            assert not _blocked(a["x"]+(b["x"]-a["x"])*t,a["y"]+(b["y"]-a["y"])*t,objects,None)
