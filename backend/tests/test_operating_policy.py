from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.services.operating_policy import FreshnessWindow, data_health

NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)
WINDOW = FreshnessWindow(valid_seconds=2, unavailable_seconds=5)


@pytest.mark.parametrize("age,expected", [(0, "VALID"), (2, "VALID"),
    (2.001, "STALE"), (5, "STALE"), (5.001, "UNAVAILABLE"), (-1, "UNAVAILABLE")])
def test_boundaries(age, expected):
    result = data_health(NOW - timedelta(seconds=age), WINDOW, now=NOW)
    assert result["state"] == expected
    assert result["verified"] is False


@pytest.mark.parametrize("stamp", [None, "bad", 123, True])
def test_missing_or_invalid_is_never_current(stamp):
    assert data_health(stamp, WINDOW, now=NOW)["state"] == "UNAVAILABLE"


def test_quality_and_time_are_separate():
    assert data_health(NOW, WINDOW, now=NOW, degraded=True)["state"] == "DEGRADED"
    assert data_health(NOW, WINDOW, now=NOW, available=False)["state"] == "UNAVAILABLE"
    assert data_health(NOW - timedelta(seconds=3), WINDOW, now=NOW, degraded=True)["state"] == "STALE"


def test_naive_database_utc_and_iso_match():
    assert data_health(NOW.replace(tzinfo=None), WINDOW, now=NOW) == data_health(NOW.isoformat(), WINDOW, now=NOW)


def test_invalid_thresholds_rejected():
    for valid, unavailable in [(5, 2), (2, 2), (0, 5), (float("nan"), 5)]:
        with pytest.raises(ValidationError):
            FreshnessWindow(valid_seconds=valid, unavailable_seconds=unavailable)
