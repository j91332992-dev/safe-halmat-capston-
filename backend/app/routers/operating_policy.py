from fastapi import APIRouter, Depends

from .auth import require_site
from ..services.operating_policy import policy, DataHealth, DetectionState, Priority, IncidentState

router = APIRouter(prefix="/api/operating-policy", tags=["operating-policy"])


@router.get("")
def get_operating_policy(site_id: str = Depends(require_site)):
    return {
        "site_id": site_id,
        "policy": policy.model_dump(mode="json"),
        "states": {name: [item.value for item in enum] for name, enum in (
            ("data_health", DataHealth), ("detection", DetectionState),
            ("priority", Priority), ("incident", IncidentState))},
        "implementation_stage": "foundation",
        "verified": False,
        "limitations": [
            "Freshness metadata is additive; legacy risk rules are not yet migrated.",
            "Battery sample and YOLO inference timestamps are not yet connected.",
            "Incident enums are contracts; persistence and escalation migration is pending.",
            "Firmware and physical hardware have not been verified against this policy.",
        ],
    }
