"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Valid alert levels: 0 = normal/test, 1 = warning, 2 = emergency
VALID_LEVELS = {0, 1, 2}


class AlertIn(BaseModel):
    """JSON body for POST /api/alert."""

    level: int = Field(..., description="0=normal, 1=warning, 2=emergency")
    device_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: int) -> int:
        if v not in VALID_LEVELS:
            raise ValueError("level must be 0, 1, or 2")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (-90.0 <= v <= 90.0):
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (-180.0 <= v <= 180.0):
            raise ValueError("longitude must be between -180 and 180")
        return v


class AlertOut(BaseModel):
    id: int
    device_id: Optional[str]
    level: int
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: datetime
    notification_type: Optional[str]
    notification_status: Optional[str]

    model_config = {"from_attributes": True}


class AlertListOut(BaseModel):
    range: str
    alerts: list[AlertOut]


class AlertResponse(BaseModel):
    success: bool
    alert_id: int
    level: int
    notification: Optional[str]
    notification_status: Optional[str]
    message: str


class StatsOut(BaseModel):
    range: str
    total: int
    level_0: int
    level_1: int
    level_2: int


class ErrorOut(BaseModel):
    error: bool = True
    detail: str
