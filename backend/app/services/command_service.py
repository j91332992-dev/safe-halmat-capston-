import json
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models.entities import CommandRecord, Device


def queue_command(db: Session, device_id: str, command_type: str, payload: dict) -> CommandRecord:
    device = db.get(Device, device_id)
    command = CommandRecord(
        command_id=str(uuid4()),
        device_id=device_id,
        site_id=device.site_id if device else "site-001",
        command_type=command_type,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(command)
    db.flush()
    return command
