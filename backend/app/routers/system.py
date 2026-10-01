from fastapi import APIRouter

from ..config import settings

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/mode")
def get_mode():
    return {"mode": settings.operation_mode}
