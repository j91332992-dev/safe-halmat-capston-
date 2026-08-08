import json
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models.entities import CommandRecord


def queue_command(db: Session, device_id: str, command_type: str, payload: dict) -> CommandRecord:
    command = CommandRecord(
        command_id=str(uuid4()),
        device_id=device_id,
        command_type=command_type,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(command)
    db.flush()
    return command

