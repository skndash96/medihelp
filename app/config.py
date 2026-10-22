"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (one level above app/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'alerts.db'}"
)

# Environment: "development" or "production"
# In development, Twilio SMS/voice calls are simulated (logged only).
APP_ENV = os.getenv("APP_ENV", "development").lower()


def is_production() -> bool:
    return APP_ENV == "production"


# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
ALERT_SMS_TO = os.getenv("ALERT_SMS_TO", "")
ALERT_CALL_TO = os.getenv("ALERT_CALL_TO", "")

# Public URL Twilio can reach for the voice TwiML (e.g. via ngrok)
TWILIO_VOICE_URL = os.getenv("TWILIO_VOICE_URL", "")

# Twilio is considered configured if the essentials for sending are present
def twilio_sms_configured() -> bool:
    return bool(
        TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER and ALERT_SMS_TO
    )


def twilio_call_configured() -> bool:
    return bool(
        TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER and ALERT_CALL_TO
    )
