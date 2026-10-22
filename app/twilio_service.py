"""Twilio integration helper.

All Twilio SDK calls live here so route handlers stay clean and the
integration can be replaced/mocked easily.
"""

import logging

logger = logging.getLogger(__name__)

SMS_WARNING_BODY = (
    "Warning: The elderly care pendant has detected a possible incident. "
    "Please check on the person."
)
VOICE_EMERGENCY_MESSAGE = (
    "Emergency alert. A possible fall has been detected. "
    "Please check on the elderly person immediately."
)


def _get_client():
    """Create (or reuse) the Twilio client if credentials are configured."""
    from twilio.rest import Client

    from app import config

    if not config.TWILIO_ACCOUNT_SID or not config.TWILIO_AUTH_TOKEN:
        raise RuntimeError("Twilio credentials are not configured.")

    return Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def send_sms(to_number: str, body: str) -> dict:
    """Send an SMS and return a small result dict.

    In development (APP_ENV != "production") the SMS is simulated: nothing is
    sent to Twilio, the message is just logged. Returns
    {'status': 'sent', 'sid': ...} on success. Raises on failure.
    """
    from app import config

    if config.is_production():
        if not config.TWILIO_FROM_NUMBER:
            raise RuntimeError("TWILIO_FROM_NUMBER is not configured.")

        client = _get_client()
        message = client.messages.create(
            body=body,
            from_=config.TWILIO_FROM_NUMBER,
            to=to_number,
        )
        logger.info("SMS sent: to=%s sid=%s", to_number, message.sid)
        return {"status": "sent", "sid": message.sid}

    # Development mode: simulate only.
    logger.info("[DEV] SMS simulated (not sent): to=%s body=%r", to_number, body)
    return {"status": "sent", "sid": "SM_dev_simulated"}


def make_voice_call(to_number: str) -> dict:
    """Initiate a Twilio voice call playing the emergency TwiML.

    In development (APP_ENV != "production") the call is simulated: nothing is
    sent to Twilio, the call is just logged. The TwiML is served by our own
    /api/twilio/voice endpoint. Returns {'status': 'sent', 'sid': ...} on
    success. Raises on failure.
    """
    from app import config

    if config.is_production():
        if not config.TWILIO_FROM_NUMBER:
            raise RuntimeError("TWILIO_FROM_NUMBER is not configured.")

        if not config.TWILIO_VOICE_URL:
            raise RuntimeError(
                "TWILIO_VOICE_URL is not configured. Expose this server with "
                "ngrok/Cloudflare Tunnel and set TWILIO_VOICE_URL to a public URL."
            )

        client = _get_client()
        call = client.calls.create(
            url=config.TWILIO_VOICE_URL,
            to=to_number,
            from_=config.TWILIO_FROM_NUMBER,
        )
        logger.info("Voice call initiated: to=%s sid=%s", to_number, call.sid)
        return {"status": "sent", "sid": call.sid}

    # Development mode: simulate only.
    logger.info("[DEV] Voice call simulated (not placed): to=%s", to_number)
    return {"status": "sent", "sid": "CA_dev_simulated"}
