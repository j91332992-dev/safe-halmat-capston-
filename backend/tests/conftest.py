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
