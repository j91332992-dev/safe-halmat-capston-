import os
from pathlib import Path
import tempfile

import pytest


TEST_DB = Path(tempfile.gettempdir()) / "hanmir_backend_pytest.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["OPERATION_MODE"] = "hardware"


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    yield
    from app.database import engine
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture(autouse=True)
def isolated_uwb_filter_state(tmp_path, monkeypatch):
    from app.config import settings
    from app.services.location_speed_service import speed_guard
    from app.services.location_filter_service import reset_location_filter
    speed_guard.reset()
    reset_location_filter()
    monkeypatch.setattr(settings, "uwb_speed_mode", "observe")
    monkeypatch.setattr(settings, "uwb_quality_mode", "observe")
    monkeypatch.setattr(settings, "uwb_filter_state_path", str(tmp_path / "distance-state.sqlite3"))
