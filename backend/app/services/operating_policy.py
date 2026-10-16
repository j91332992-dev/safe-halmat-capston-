"""Versioned PRD foundation. Freshness is not hardware verification."""
from datetime import datetime, timezone
from enum import Enum
from math import isfinite

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..config import BASE_DIR


class DataHealth(str, Enum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class DetectionState(str, Enum):
    NORMAL = "NORMAL"
    SUSPECT = "SUSPECT"
    CONFIRMED = "CONFIRMED"
    CLEARED = "CLEARED"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IncidentState(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class FreshnessWindow(BaseModel):
    valid_seconds: float = Field(gt=0, allow_inf_nan=False)
    unavailable_seconds: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered(self):
        if self.unavailable_seconds <= self.valid_seconds:
            raise ValueError("unavailable_seconds must exceed valid_seconds")
        return self


class OperatingPolicy(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPS_", env_nested_delimiter="__",
        env_file=BASE_DIR / ".env", extra="ignore",
    )
    version: str = "2026-10-16.foundation.1"
    heading: FreshnessWindow = FreshnessWindow(valid_seconds=2, unavailable_seconds=5)
    uwb: FreshnessWindow = FreshnessWindow(valid_seconds=2, unavailable_seconds=5)
    camera: FreshnessWindow = FreshnessWindow(valid_seconds=3, unavailable_seconds=10)
    yolo: FreshnessWindow = FreshnessWindow(valid_seconds=3, unavailable_seconds=10)
    battery: FreshnessWindow = FreshnessWindow(valid_seconds=15, unavailable_seconds=30)
    heartbeat: FreshnessWindow = FreshnessWindow(valid_seconds=15, unavailable_seconds=30)


policy = OperatingPolicy()


def data_health(observed_at, window: FreshnessWindow, *, now=None,
                available=True, degraded=False, age_basis="server_receipt") -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = None
    reason = "MISSING_TIMESTAMP"
    try:
        if isinstance(observed_at, str):
            observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if isinstance(observed_at, datetime):
            stamp = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=timezone.utc)
            age = (now - stamp).total_seconds()
            reason = "FUTURE_TIMESTAMP" if age < 0 else "FRESH"
    except (TypeError, ValueError, OverflowError):
        reason = "INVALID_TIMESTAMP"
    state = DataHealth.UNAVAILABLE
    if age is not None and isfinite(age) and age >= 0:
        if not available:
            reason = "SOURCE_UNAVAILABLE"
        elif age > window.unavailable_seconds:
            reason = "DATA_EXPIRED"
        elif age > window.valid_seconds:
            state, reason = DataHealth.STALE, "DATA_STALE"
        elif degraded:
            state, reason = DataHealth.DEGRADED, "SOURCE_DEGRADED"
        else:
            state = DataHealth.VALID
    return {"state": state.value, "age_seconds": age, "age_basis": age_basis,
            "reason_code": reason, "policy_version": policy.version,
            "verified": False, "verification_status": "UNVERIFIED"}
