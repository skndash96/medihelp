"""Shared pytest fixtures.

We point the app at a temporary SQLite database and mock the Twilio layer so
tests never make real SMS/voice calls.
"""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Must be set before importing app modules.
_tmp = tempfile.mkdtemp(prefix="fallalert_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["TWILIO_ACCOUNT_SID"] = "AC_test_sid"
os.environ["TWILIO_AUTH_TOKEN"] = "test_token"
os.environ["TWILIO_FROM_NUMBER"] = "+15551234567"
os.environ["ALERT_SMS_TO"] = "+15551112222"
os.environ["ALERT_CALL_TO"] = "+15553334444"
os.environ["TWILIO_VOICE_URL"] = "https://example.ngrok.io/api/twilio/voice"

from app.main import app  # noqa: E402
from app.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    """Create a fresh schema for each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _mock_twilio(monkeypatch):
    """Mock the Twilio service so no real calls/SMS are made.

    The real send_sms/make_voice_call are exposed as
    `_real_twilio_send_sms` / `_real_twilio_make_voice_call` for tests that
    specifically exercise the simulation code paths.
    """
    from app import twilio_service

    # Expose the real functions for tests that exercise the simulation paths.
    twilio_service._real_twilio_send_sms = twilio_service.send_sms
    twilio_service._real_twilio_make_voice_call = twilio_service.make_voice_call

    def fake_send_sms(to, body):
        return {"status": "sent", "sid": "SM_test"}

    def fake_make_voice_call(to):
        return {"status": "sent", "sid": "CA_test"}

    monkeypatch.setattr(twilio_service, "send_sms", fake_send_sms)
    monkeypatch.setattr(twilio_service, "make_voice_call", fake_make_voice_call)
