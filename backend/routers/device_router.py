from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter(tags=["devices"])


class DeviceResponse(BaseModel):
    id: int
    device: str
    type: str
    size: str
    serial: str
    last_seen_at: str


@router.get("/devices", response_model=list[DeviceResponse])
def list_devices(
    request: Request,
    db: Session = Depends(get_db),
) -> list[DeviceResponse]:
    detector = request.app.state.device_detector
    return [DeviceResponse.model_validate(item) for item in detector.list_devices(db)]
