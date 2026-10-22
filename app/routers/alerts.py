"""Alert, history and statistics API endpoints."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config, twilio_service
from app.database import get_db
from app.models import Alert
from app.schemas import (
    AlertIn,
    AlertListOut,
    AlertOut,
    AlertResponse,
    StatsOut,
    VALID_LEVELS,
)
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["alerts"])

# How far back each supported range reaches (in seconds/as timedelta)
RANGES = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
    "1m": timedelta(days=30),
}

from app import config, twilio_service
from app.database import get_db
from app.models import Alert
from app.schemas import (
    AlertIn,
    AlertListOut,
    AlertOut,
    AlertResponse,
    StatsOut,
    VALID_LEVELS,
)

# Twilio message bodies (single source of truth in twilio_service)
from app.twilio_service import SMS_WARNING_BODY, VOICE_EMERGENCY_MESSAGE



def _range_delta(range_key: str) -> timedelta:
    if range_key not in RANGES:
        raise HTTPException(
            status_code=400, detail=f"Unknown range '{range_key}'. Use one of: {', '.join(RANGES)}"
        )
    return RANGES[range_key]


def _store_alert(db: Session, level: int, device_id, latitude, longitude) -> Alert:
    alert = Alert(
        level=level,
        device_id=device_id,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    logger.info("Alert stored: id=%s", alert.id)
    return alert


def _send_notification(alert: Alert):
    """Send the appropriate Twilio notification for the alert level.

    Returns (notification_type, notification_status). Never raises: on
    Twilio failure the alert is still kept and status='failed'.
    """
    if alert.level == 1:
        notification_type = "sms"
        try:
            result = twilio_service.send_sms(config.ALERT_SMS_TO, SMS_WARNING_BODY)
            logger.info("Alert %s: SMS sent", alert.id)
            return notification_type, result.get("status", "sent")
        except Exception as exc:  # noqa: BLE001 - record the failure
            logger.error("Twilio SMS failed for alert=%s: %s", alert.id, exc)
            return notification_type, "failed"

    if alert.level == 2:
        notification_type = "voice_call"
        try:
            result = twilio_service.make_voice_call(config.ALERT_CALL_TO)
            logger.info("Alert %s: voice call initiated", alert.id)
            return notification_type, result.get("status", "sent")
        except Exception as exc:  # noqa: BLE001 - record the failure
            logger.error("Twilio voice call failed for alert=%s: %s", alert.id, exc)
            return notification_type, "failed"

    # Level 0: store only, no notification
    return None, None


def _post_alert(
    db: Session,
    level: int,
    device_id: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
) -> AlertResponse:
    logger.info("Alert received: level=%s device=%s", level, device_id)

    alert = _store_alert(db, level, device_id, latitude, longitude)
    notification_type, notification_status = _send_notification(alert)

    # Persist the notification outcome
    alert.notification_type = notification_type
    alert.notification_status = notification_status
    db.commit()

    failed = notification_status == "failed"
    return AlertResponse(
        success=not failed,
        alert_id=alert.id,
        level=level,
        notification=notification_type,
        notification_status=notification_status,
        message=(
            "Alert recorded, but Twilio notification failed."
            if failed
            else "OK"
        ),
    )


@router.get("/alert", response_model=AlertResponse)
@router.post("/alert", response_model=AlertResponse)
async def create_alert(
    payload: Optional[AlertIn] = None,
    level: Optional[int] = Query(None),
    device_id: Optional[str] = Query(None),
    lat: Optional[float] = Query(None, description="latitude"),
    lon: Optional[float] = Query(None, description="longitude"),
    db: Session = Depends(get_db),
):
    """Create a new alert.

    Supports both a JSON body and query parameters (for the future ESP32):
        POST /api/alert                 with JSON {"level": 2, ...}
        POST /api/alert?level=2&lat=10.79&lon=78.70
    """
    # Build a single validated payload from either source.
    if payload is not None:
        if level is not None or lat is not None or lon is not None:
            raise HTTPException(
                status_code=400,
                detail="Do not mix a JSON body with query parameters.",
            )
        data = payload
    else:
        # Query-parameter path: treat missing level as invalid.
        if level is None:
            raise HTTPException(status_code=422, detail="'level' is required.")
        if level not in VALID_LEVELS:
            raise HTTPException(status_code=422, detail="level must be 0, 1, or 2.")
        # Validate coordinates
        if lat is not None and not (-90.0 <= lat <= 90.0):
            raise HTTPException(status_code=422, detail="latitude must be between -90 and 90")
        if lon is not None and not (-180.0 <= lon <= 180.0):
            raise HTTPException(status_code=422, detail="longitude must be between -180 and 180")
        data = AlertIn(level=level, device_id=device_id, latitude=lat, longitude=lon)

    response = _post_alert(
        db,
        data.level,
        data.device_id,
        data.latitude,
        data.longitude,
    )
    # A failed notification is still a successful alert *storage*, so we
    # report 200 but flag failure in the body. Twilio config errors are
    # surfaced there rather than as 5xx.
    return response


@router.get("/alerts", response_model=AlertListOut)
async def list_alerts(
    range: str = Query("1h"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return alerts within the requested time range, newest first."""
    delta = _range_delta(range)
    since = datetime.now(timezone.utc) - delta

    stmt = (
        select(Alert)
        .where(Alert.created_at >= since)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    alerts = db.execute(stmt).scalars().all()
    return AlertListOut(range=range, alerts=[AlertOut.model_validate(a) for a in alerts])


@router.get("/alerts/latest", response_model=AlertListOut)
async def latest_alerts(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return the most recent alerts regardless of time range."""
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    alerts = db.execute(stmt).scalars().all()
    return AlertListOut(range="latest", alerts=[AlertOut.model_validate(a) for a in alerts])


@router.get("/stats", response_model=StatsOut)
async def stats(
    range: str = Query("1d"),
    db: Session = Depends(get_db),
):
    """Return counts of alerts by level within the requested range."""
    delta = _range_delta(range)
    since = datetime.now(timezone.utc) - delta

    rows = db.execute(
        select(Alert.level, func.count(Alert.id))
        .where(Alert.created_at >= since)
        .group_by(Alert.level)
    ).all()

    counts = {0: 0, 1: 0, 2: 0}
    for level, count in rows:
        counts[level] = count

    return StatsOut(
        range=range,
        total=sum(counts.values()),
        level_0=counts[0],
        level_1=counts[1],
        level_2=counts[2],
    )


@router.get(
    "/twilio/voice",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/plain": {}}}},
)
@router.post(
    "/twilio/voice",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/plain": {}}}},
)
async def twilio_voice():
    """Return TwiML instructing Twilio what to say during the emergency call.

    To switch to a prerecorded message later, replace the <Say> block with:
        <Play>https://example.com/recorded-message.wav</Play>
    The rest of the alert flow is unchanged.
    """
    logger.info("Voice TwiML requested")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>{VOICE_EMERGENCY_MESSAGE}</Say>
</Response>"""
    return PlainTextResponse(twiml, media_type="application/xml")
