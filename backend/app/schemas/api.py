from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DeviceRegister(BaseModel):
    organization_id: str = "org-001"
    site_id: str = "site-001"
    worker_id: str
    helmet_id: str
    device_id: str
    device_type: Literal["assistant_device", "position_device", "uwb_anchor"]
    firmware_version: str = "0.1.0"
    ip: str | None = None
    mac: str | None = None


class Heartbeat(BaseModel):
    organization_id: str = "org-001"
    site_id: str = "site-001"
    worker_id: str
    helmet_id: str
    device_id: str
    rssi: int | None = None
    battery: float | None = Field(default=None, ge=0, le=100)
    component_status: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ButtonEventIn(BaseModel):
    organization_id: str = "org-001"
    site_id: str = "site-001"
    worker_id: str
    helmet_id: str
    device_id: str
    event_type: Literal["single_press", "double_press", "triple_press", "long_press"]
    occurred_at: datetime | None = None


class DistanceMeasurement(BaseModel):
    anchor_id: str
    distance_m: float = Field(gt=0, lt=100)
    quality: float = Field(default=1.0, ge=0, le=1)


class UwbDistancesIn(BaseModel):
    organization_id: str = "org-001"
    site_id: str = "site-001"
    worker_id: str
    helmet_id: str
    device_id: str
    uwb_tag_id: str
    measurements: list[DistanceMeasurement] = Field(min_length=3)


class AnchorIn(BaseModel):
    anchor_id: str
    name: str
    x: float
    y: float
    z: float = 2.0
    online: bool = True


class ZoneIn(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: Literal["rectangle", "circle", "polygon"] = "rectangle"
    coordinates: dict[str, Any]
    required_ppe: list[str] = Field(default_factory=list)
    risk_weight: int = Field(default=30, ge=0, le=100)
    warning_message: str = "위험구역입니다."
    max_stay_seconds: int = 0
    active: bool = True


class MockDetectionIn(BaseModel):
    worker_id: str = "worker-001"
    device_id: str = "helmet-001-av"
    vest: bool = True
    glove: bool = True
    fire: bool = False
    smoke: bool = False


class MockCommandIn(BaseModel):
    worker_id: str = "worker-001"
    device_id: str = "helmet-001-av"
    text: str = "현재 위험도 알려줘"


class DeviceCommandIn(BaseModel):
    command_type: Literal["play_tone", "play_alert", "set_volume", "stop_alert", "request_status", "record_audio"]
    payload: dict[str, Any] = Field(default_factory=dict)


class SystemModeIn(BaseModel):
    mode: Literal["mock", "hardware"]


class MockScenarioIn(BaseModel):
    scenario: Literal["normal", "danger_zone", "ppe_missing", "fire", "smoke", "emergency", "device_offline"]
    worker_id: str = "worker-001"

