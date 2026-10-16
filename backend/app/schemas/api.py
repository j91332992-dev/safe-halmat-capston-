from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator


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


class ComponentResultIn(BaseModel):
    component: Literal["speaker"]
    status: Literal["ok", "error"]
    command_id: str | None = None
    detail: str | None = None


class HeadingCalibrationIn(BaseModel):
    anchor_ids: tuple[str, str] = ("anchor-001", "anchor-004")


class ButtonEventIn(BaseModel):
    organization_id: str = "org-001"
    site_id: str = "site-001"
    worker_id: str
    helmet_id: str
    device_id: str
    event_type: Literal["single_press", "double_press", "triple_press", "long_press"]
    occurred_at: datetime | None = None


class UwbDiagnostics(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="allow")
    status: Literal["valid", "missing", "invalid"] = "missing"
    reason: str | None = Field(default=None, max_length=128)
    direction: Literal["anchor_to_tag"] = "anchor_to_tag"
    sequence: Literal["ipatov"] = "ipatov"
    rx_power_dbm: float | None = None
    first_path_power_dbm: float | None = None
    power_difference_db: float | None = None
    peak_minus_first_path_samples: float | None = None
    clock_offset_ppm: float | None = None
    raw: dict[str, int | float | bool | None] = Field(default_factory=dict, max_length=32)

    @model_validator(mode="after")
    def explicit_validity(self):
        derived = (self.rx_power_dbm, self.first_path_power_dbm,
                   self.power_difference_db, self.peak_minus_first_path_samples, self.clock_offset_ppm)
        if self.status == "valid" and any(value is None for value in derived):
            raise ValueError("valid diagnostics require all derived values")
        if self.status != "valid" and any(value is not None for value in derived[:4]):
            raise ValueError("missing/invalid power diagnostics must use null")
        return self


class RangeObservation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    anchor_id: str = Field(max_length=64)
    anchor_hw_id: int | None = None
    status: Literal["valid", "missing", "invalid"]
    raw_distance_m: float | None = None
    legacy_range_cm: int | None = None
    measured_uptime_us: int | None = Field(default=None, ge=0)
    rx_timestamp_dtu: int | None = Field(default=None, ge=0, lt=2**40)
    diagnostics: UwbDiagnostics = Field(default_factory=UwbDiagnostics)


class DistanceMeasurement(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    anchor_id: str = Field(max_length=64)
    distance_m: float = Field(gt=0, lt=100)
    quality: float = Field(default=1.0, ge=0, le=1)
    raw_distance_m: float | None = None
    median_distance_m: float | None = None
    calibration_offset_m: float | None = None
    held: bool = False
    source_measurement_id: str | None = Field(default=None, max_length=192)
    diagnostics: UwbDiagnostics = Field(default_factory=UwbDiagnostics)


class UwbDistancesIn(BaseModel):
    organization_id: str = "org-001"
    site_id: str = "site-001"
    worker_id: str
    helmet_id: str
    device_id: str
    uwb_tag_id: str = Field(max_length=128)
    distances_calibrated: bool = True
    schema_version: int = 1
    firmware_version: str | None = Field(default=None, max_length=128)
    source_revision: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    measurement_id: str | None = Field(default=None, max_length=192)
    cycle_id: int | None = Field(default=None, ge=0)
    sequence: int | None = Field(default=None, ge=0, le=255)
    tag_hw_id: int | None = None
    measured_uptime_us: int | None = Field(default=None, ge=0)
    measured_at: datetime | None = None
    time_basis: str | None = Field(default=None, max_length=64)
    firmware_dropped_cycles: int = Field(default=0, ge=0)
    transport: Literal["usb", "wifi", "wifi-ws", "legacy"] = "legacy"
    bridge_received_at: datetime | None = None
    bridge_capture_id: str | None = Field(default=None, max_length=64)
    observations: list[RangeObservation] = Field(default_factory=list, max_length=16)
    measurements: list[DistanceMeasurement] = Field(max_length=16)

    @model_validator(mode="after")
    def distinct_anchors(self):
        for rows in (self.observations, self.measurements):
            if len({row.anchor_id for row in rows}) != len(rows):
                raise ValueError("duplicate anchor_id in frame")
        if self.schema_version >= 2 and not all(value is not None for value in
                (self.session_id, self.measurement_id, self.cycle_id, self.measured_uptime_us)):
            raise ValueError("schema v2 requires session, measurement, cycle and device uptime")
        return self


class AnchorIn(BaseModel):
    anchor_id: str
    name: str
    x: float
    y: float
    z: float = 2.0
    online: bool = False


class ZoneIn(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: Literal["rectangle", "circle", "polygon"] = "rectangle"
    zone_category: Literal["general", "danger", "controlled", "confined", "safe", "rest", "shadow"] = "danger"
    coordinates: dict[str, Any]
    required_ppe: list[str] = Field(default_factory=list)
    allowed_worker_ids: list[str] = Field(default_factory=list)
    risk_weight: int = Field(default=30, ge=0, le=100)
    warning_message: str = "위험구역입니다."
    max_stay_seconds: int = 0
    active: bool = True


class TextCommandIn(BaseModel):
    worker_id: str = "worker-001"
    device_id: str = "helmet-001-av"
    text: str = Field(min_length=1, max_length=2000)
    sound_db: float | None = Field(default=None, ge=0, le=180)


class DeviceCommandIn(BaseModel):
    command_type: Literal["play_tone", "play_alert", "play_audio", "play_ack", "set_volume", "stop_alert", "start_call_ringing", "stop_call_ringing", "request_status", "record_audio", "set_camera_timeout"]
    payload: dict[str, Any] = Field(default_factory=dict)


class SiteLayoutIn(BaseModel):
    name: str = Field(default="한미르 테스트 작업장", min_length=1, max_length=100)
    width: float = Field(gt=0.5, le=1000)
    height: float = Field(gt=0.5, le=1000)


class ObstacleIn(BaseModel):
    obstacle_id: str
    name: str = Field(min_length=1, max_length=100)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0.05)
    height: float = Field(gt=0.05)
    object_type: Literal["obstacle", "wall", "emergency_exit", "door"] = "obstacle"

class LayoutDraftIn(BaseModel):
    site: SiteLayoutIn
    anchors: list[AnchorIn]
    obstacles: list[ObstacleIn]
    zones: list[ZoneIn]

class LayoutVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class WorkerUpdateIn(BaseModel):
    worker_name: str = Field(min_length=1, max_length=80)
    worker_role: Literal["general_worker", "manager", "hot_work_authorized", "heavy_equipment_operator", "unauthorized"] = "general_worker"
    notes: str = Field(default="", max_length=2000)


class FireZoneIn(BaseModel):
    name: str = Field(default="관리자 지정 화재구역", min_length=1, max_length=80)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0.05)
    height: float = Field(gt=0.05)


class FireTriggerIn(BaseModel):
    worker_id: str = "worker-001"
    source: Literal["voice", "yolo", "manager"] = "manager"
    details: dict[str, Any] = Field(default_factory=dict)


class FireCancelIn(BaseModel):
    reason: Literal["false_alarm", "no_fire", "resolved"] = "false_alarm"
