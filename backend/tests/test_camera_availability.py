import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.entities import Event
from app.routers import camera


def test_missing_capture_is_not_advertised_and_new_frame_recovers(tmp_path, monkeypatch):
    monkeypatch.setattr(camera, 'CAPTURE_DIR', tmp_path)
    monkeypatch.setattr(camera, '_latest_analysis_cache', {})
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        event = Event(event_id='old-frame', event_type='CAMERA_FRAME', device_id='helmet-test',
                      site_id='site-test', severity='info', message='frame',
                      details_json=json.dumps({'filename': 'missing.jpg'}))
        db.add(event)
        db.commit()
        assert camera.latest_frame('helmet-test', db)['received'] is False
        # A newly received analyzed frame must recover even if the old file is gone.
        camera._latest_analysis_cache['helmet-test'] = (b'jpeg', {
            'filename': 'new.jpg', 'frame_id': 42, 'analyzed_at': datetime.now().isoformat(),
        })
        status = camera.latest_frame('helmet-test', db)
        assert status['received'] is True
        assert status['frame_id'] == 42
        assert camera.latest_frame_image('helmet-test', db).body == b'jpeg'


def test_existing_saved_frame_has_stable_version(tmp_path, monkeypatch):
    monkeypatch.setattr(camera, 'CAPTURE_DIR', tmp_path)
    monkeypatch.setattr(camera, '_latest_analysis_cache', {})
    (tmp_path / 'saved.jpg').write_bytes(b'jpeg')
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Event(event_id='saved-frame', event_type='CAMERA_FRAME', device_id='helmet-test',
                     site_id='site-test', severity='info', message='frame',
                     details_json=json.dumps({'filename': 'saved.jpg'})))
        db.commit()
        first = camera.latest_frame('helmet-test', db)
        assert first['received'] is True
        assert first['analyzed_at'] == camera.latest_frame('helmet-test', db)['analyzed_at']
