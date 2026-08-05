from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, utcnow


class Device(Base):
    __tablename__ = "devices"
    device_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    device_type: Mapped[str] = mapped_column(String(40))
    organization_id: Mapped[str] = mapped_column(String(40), default="org-001")
    site_id: Mapped[str] = mapped_column(String(40), default="site-001")
    worker_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    helmet_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    battery: Mapped[float | None] = mapped_column(Float, nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    component_status_json: Mapped[str] = mapped_column(Text, default="{}")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_camera_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_audio_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_button_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_uwb_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_speaker_status: Mapped[str | None] = mapped_column(String(80), nullable=True)


class WorkerState(Base):
    __tablename__ = "worker_states"
    worker_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    worker_name: Mapped[str] = mapped_column(String(80), default="작업자")
    notes: Mapped[str] = mapped_column(Text, default="")
    helmet_id: Mapped[str] = mapped_column(String(40))
    x: Mapped[float] = mapped_column(Float, default=0)
    y: Mapped[float] = mapped_column(Float, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    current_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(20), default="정상")
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    ppe_json: Mapped[str] = mapped_column(Text, default="{}")
    hazard_json: Mapped[str] = mapped_column(Text, default="{}")
    emergency: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Anchor(Base):
    __tablename__ = "anchors"
    anchor_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    z: Mapped[float] = mapped_column(Float, default=2.0)
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Zone(Base):
    __tablename__ = "zones"
    zone_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    zone_name: Mapped[str] = mapped_column(String(100))
    zone_type: Mapped[str] = mapped_column(String(30), default="rectangle")
    coordinates_json: Mapped[str] = mapped_column(Text)
    required_ppe_json: Mapped[str] = mapped_column(Text, default="[]")
    allowed_worker_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    risk_weight: Mapped[int] = mapped_column(Integer, default=30)
    warning_message: Mapped[str] = mapped_column(Text, default="위험구역입니다.")
    max_stay_seconds: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class LayoutVersion(Base):
    __tablename__ = "layout_versions"
    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(40), default="site-001", index=True)
    name: Mapped[str] = mapped_column(String(100))
    design_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class LayoutDraft(Base):
    __tablename__ = "layout_drafts"
    site_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    draft_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class SiteLayout(Base):
    __tablename__ = "site_layouts"
    site_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="한미르 테스트 작업장")
    width: Mapped[float] = mapped_column(Float, default=5.8)
    height: Mapped[float] = mapped_column(Float, default=8.2)


class Obstacle(Base):
    __tablename__ = "obstacles"
    obstacle_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(40), default="site-001", index=True)
    name: Mapped[str] = mapped_column(String(100))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    width: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)

class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String(40), index=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    distances_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Event(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class VoiceCommand(Base):
    __tablename__ = "voice_commands"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String(40))
    device_id: Mapped[str] = mapped_column(String(80))
    original_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(60))
    confidence: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CommandRecord(Base):
    __tablename__ = "command_records"
    command_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(80), index=True)
    command_type: Mapped[str] = mapped_column(String(40))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

