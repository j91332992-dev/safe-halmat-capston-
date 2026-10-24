import copy
from datetime import timedelta
import math

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.entities import AnchorSurvey, SurveyCoordinator
from app.routers.auth import require_site
from app.services.anchor_survey_service import evaluate

TOKEN='local-survey-test-token'
HEADERS={'Authorization':'Bearer '+TOKEN}
ANCHORS=[dict(z=1) for _ in range(4)]


def samples():
    points=[(0,0),(4,0),(4,3),(0,3)]
    result=[]
    for a in range(1,5):
        for b in range(a+1,5):
            distance=math.dist(points[a-1],points[b-1])
            for i in range(16):
                result.append(dict(a=a,b=b,sequence=i,elapsed_ms=i*625,
                    distance_m=distance+(i%3-1)*.005,diagnostic_valid=True,gap_db=3,path_samples=1))
    return result


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings,'uwb_survey_device_token',TOKEN)
    monkeypatch.setattr(settings,'uwb_survey_site_id','site-001')
    app.dependency_overrides[require_site]=lambda:'site-001'
    with TestClient(app) as c:
        with SessionLocal() as db:
            db.query(AnchorSurvey).delete();db.query(SurveyCoordinator).delete();db.commit()
        yield c
    app.dependency_overrides.pop(require_site,None)


def start(client):
    r=client.post('/api/anchor-survey/device/poll',headers=HEADERS,json=dict(protocol=1,firmware='test'))
    assert r.status_code==200
    r=client.post('/api/anchor-survey/start',json=dict(corners_confirmed=True,heights_confirmed=True))
    assert r.status_code==200,r.text
    command=client.post('/api/anchor-survey/device/poll',headers=HEADERS,json=dict(protocol=1,firmware='test')).json()
    return command


def test_device_resource_counters_are_optional_and_bounded(client):
    payload=dict(protocol=1,firmware='anchor-survey-v2-ds',heap_free_bytes=180000,
                 heap_min_bytes=90000,stack_high_watermark_raw=7000)
    assert client.post('/api/anchor-survey/device/poll',headers=HEADERS,json=payload).status_code==200
    resources=client.get('/api/anchor-survey').json()['coordinator_resources']
    assert resources['heap_free_bytes']==180000
    assert resources['heap_min_bytes']==90000
    assert resources['stack_high_watermark_raw']==7000
    assert resources['recorded_at'].endswith('Z')
    assert client.post('/api/anchor-survey/device/poll',headers=HEADERS,
        json=dict(protocol=1,firmware='legacy')).status_code==200
    payload['heap_free_bytes']=-1
    assert client.post('/api/anchor-survey/device/poll',headers=HEADERS,json=payload).status_code==422


def finish(client,command):
    session=command['session_id']
    r=client.post(f'/api/anchor-survey/device/{session}/begin',headers=HEADERS,json=dict(nonce=command['nonce'],ready_mask=15))
    assert r.status_code==200,r.text
    with SessionLocal() as db:
        row=db.get(AnchorSurvey,session);row.started_at-=timedelta(seconds=10);db.commit()
    return client.post(f'/api/anchor-survey/device/{session}/complete',headers=HEADERS,
        json=dict(nonce=command['nonce'],completed=True,duration_ms=10000,samples=samples()))


def test_robust_estimator_rejects_isolated_spikes():
    data=samples()
    data.append(dict(data[0],sequence=99,elapsed_ms=9800,distance_m=20))
    r=evaluate(data,ANCHORS)
    assert r['passed'] and abs(r['width']-4)<.02 and abs(r['height']-3)<.02
    assert r['pairs'][0]['count']==16 and r['pairs'][0]['total']==17
    assert r['pairs'][0]['estimator']=='huber_signal_weighted'


def test_two_substantial_modes_are_not_arbitrarily_selected():
    data=samples()
    for s in data:
        if s['a']==1 and s['b']==2 and s['sequence']>=8:s['distance_m']+=.7
    r=evaluate(data,ANCHORS)
    assert not r['passed'] and r['pairs'][0]['multimodal']


def test_diagonal_inconsistency_and_missing_pair_reject():
    data=[s for s in samples() if (s['a'],s['b'])!=(2,4)]
    assert not evaluate(data,ANCHORS)['passed']


def test_height_correction_is_applied():
    anchors=[dict(z=z) for z in [1,1.4,1.2,1]]
    data=samples()
    for s in data:
        dz=anchors[s['a']-1]['z']-anchors[s['b']-1]['z']
        s['distance_m']=math.hypot(s['distance_m'],dz)
    r=evaluate(data,anchors)
    assert r['passed'] and abs(r['width']-4)<.02 and abs(r['height']-3)<.02


def test_start_is_blocked_without_capable_coordinator(client):
    assert not client.get('/api/anchor-survey').json()['supported']
    r=client.post('/api/anchor-survey/start',json=dict(corners_confirmed=True,heights_confirmed=True))
    assert r.status_code==409
    assert client.post('/api/anchor-survey/device/poll',json=dict(protocol=1,firmware='fake')).status_code==401


def test_measurement_never_changes_live_map_until_admin_import_and_apply(client):
    before=client.get('/api/layout').json()
    command=start(client)
    r=finish(client,command)
    assert r.status_code==200 and r.json()['status']=='ready',r.text
    assert client.get('/api/layout').json()==before
    imported=client.post(f"/api/anchor-survey/{command['session_id']}/import")
    assert imported.status_code==200,imported.text
    assert imported.json()['draft']['site']['width']==pytest.approx(4,abs=.02)
    assert client.get('/api/layout').json()==before
    assert client.post(f"/api/anchor-survey/{command['session_id']}/import").status_code==409


def test_missing_ready_anchor_cannot_begin_and_nonce_is_checked(client):
    c=start(client);url=f"/api/anchor-survey/device/{c['session_id']}/begin"
    assert client.post(url,headers=HEADERS,json=dict(nonce=c['nonce'],ready_mask=7)).status_code==409
    assert client.post(url,headers=HEADERS,json=dict(nonce='wrong',ready_mask=15)).status_code==409


def test_draft_conflict_blocks_import(client):
    c=start(client);assert finish(client,c).json()['status']=='ready'
    draft=client.get('/api/layout/draft').json();draft['site']['name']='changed after survey'
    assert client.put('/api/layout/draft',json=draft).status_code==200
    assert client.post(f"/api/anchor-survey/{c['session_id']}/import").status_code==409


def test_cancelled_session_cannot_upload_or_import(client):
    c=start(client)
    assert client.post(f"/api/anchor-survey/{c['session_id']}/cancel").status_code==200
    assert client.post(f"/api/anchor-survey/{c['session_id']}/import").status_code==409
    r=client.post(f"/api/anchor-survey/device/{c['session_id']}/complete",headers=HEADERS,
        json=dict(nonce=c['nonce'],completed=True,duration_ms=10000,samples=samples()))
    assert r.status_code==409


def test_old_survey_from_another_site_is_hidden(client):
    c=start(client)
    app.dependency_overrides[require_site]=lambda:'site-other'
    assert client.post(f"/api/anchor-survey/{c['session_id']}/import").status_code==404


def test_missing_device_ack_times_out_without_success(client):
    c=start(client)
    with SessionLocal() as db:
        row=db.get(AnchorSurvey,c['session_id']);row.created_at-=timedelta(seconds=31);db.commit()
    assert client.get('/api/anchor-survey').json()['session']['status']=='timed_out'


def test_premature_complete_is_rejected_and_never_updates_map(client):
    c=start(client)
    assert client.post(f"/api/anchor-survey/device/{c['session_id']}/begin",headers=HEADERS,
                       json=dict(nonce=c['nonce'],ready_mask=15)).status_code==200
    result=client.post(f"/api/anchor-survey/device/{c['session_id']}/complete",headers=HEADERS,
        json=dict(nonce=c['nonce'],completed=True,duration_ms=10000,samples=samples())).json()
    assert result['status']=='rejected'


def test_fire_cancels_running_survey(client):
    from app.models.entities import EvacuationIncident
    c=start(client)
    with SessionLocal() as db:
        db.add(EvacuationIncident(incident_id='survey-test-fire',site_id='site-001',source='test',status='active'));db.commit()
    try:
        assert client.post('/api/anchor-survey/device/poll',headers=HEADERS,
            json=dict(protocol=1,firmware='test')).json()['command']=='idle'
        assert client.get('/api/anchor-survey').json()['session']['status']=='cancelled'
    finally:
        with SessionLocal() as db:
            db.query(EvacuationIncident).filter_by(incident_id='survey-test-fire').delete();db.commit()


def test_outside_objects_block_apply_instead_of_silent_clipping(client):
    draft=client.get('/api/layout/draft').json()
    draft['obstacles']=[dict(obstacle_id='outside-object',name='outside',object_type='obstacle',
        x=100,y=100,width=1,height=1)]
    assert client.put('/api/layout/draft',json=draft).status_code==200
    before=client.get('/api/layout').json()
    r=client.post('/api/layout/apply')
    assert r.status_code==409
    assert client.get('/api/layout').json()==before
