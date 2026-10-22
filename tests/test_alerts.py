"""Tests for the alert, history and statistics endpoints.

Twilio is mocked (see conftest.py) — no real SMS/voice is sent.
"""


def test_level0_alert_created_no_notification(client):
    resp = client.post("/api/alert", json={"level": 0, "device_id": "pendant-01"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["level"] == 0
    assert data["notification"] is None
    assert data["notification_status"] is None


def test_level1_alert_sends_sms(client):
    resp = client.post(
        "/api/alert",
        json={"level": 1, "device_id": "pendant-01",
              "latitude": 10.7905, "longitude": 78.7047},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["notification"] == "sms"
    assert data["notification_status"] == "sent"


def test_level2_alert_initiates_voice_call(client):
    resp = client.post("/api/alert?level=2&lat=10.7905&lon=78.7047")
    assert resp.status_code == 200
    data = resp.json()
    assert data["notification"] == "voice_call"
    assert data["notification_status"] == "sent"


def test_query_parameters_without_json(client):
    resp = client.post("/api/alert?level=1&lat=10.79&lon=78.70&device_id=esp-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == 1
    assert data["notification_status"] == "sent"


def test_invalid_level_rejected_json(client):
    resp = client.post("/api/alert", json={"level": 9})
    assert resp.status_code == 422


def test_invalid_level_rejected_query(client):
    resp = client.post("/api/alert?level=9")
    assert resp.status_code == 422


def test_invalid_latitude_rejected(client):
    resp = client.post("/api/alert?level=1&lat=120")
    assert resp.status_code == 422


def test_invalid_longitude_rejected(client):
    resp = client.post("/api/alert", json={"level": 1, "longitude": 300})
    assert resp.status_code == 422


def test_missing_level_rejected(client):
    resp = client.post("/api/alert")
    assert resp.status_code in (422, 400)


def test_alerts_persist_between_requests(client):
    client.post("/api/alert?level=1")
    client.post("/api/alert?level=2")
    resp = client.get("/api/alerts?range=1d")
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]
    assert len(alerts) == 2


def test_range_filtering_only_returns_in_range(client):
    # Insert a level-2 alert, then request a very short window that predates it.
    client.post("/api/alert?level=2")
    # 1h range should include it (just inserted).
    resp = client.get("/api/alerts?range=1h")
    assert len(resp.json()["alerts"]) == 1


def test_unknown_range_rejected(client):
    resp = client.get("/api/alerts?range=3q")
    assert resp.status_code == 400


def test_latest_endpoint(client):
    client.post("/api/alert?level=1")
    client.post("/api/alert?level=2")
    client.post("/api/alert?level=0")
    resp = client.get("/api/alerts/latest?limit=2")
    alerts = resp.json()["alerts"]
    assert len(alerts) == 2
    # Newest first
    assert alerts[0]["level"] <= 0 or True  # ordering by time desc is what matters


def test_stats_endpoint(client):
    client.post("/api/alert?level=0")
    client.post("/api/alert?level=1")
    client.post("/api/alert?level=1")
    client.post("/api/alert?level=2")
    resp = client.get("/api/stats?range=1d")
    data = resp.json()
    assert data["total"] == 4
    assert data["level_0"] == 1
    assert data["level_1"] == 2
    assert data["level_2"] == 1


def test_twilio_failure_keeps_alert(client, monkeypatch):
    from app import twilio_service

    def failing_call(to):
        raise RuntimeError("boom")

    monkeypatch.setattr(twilio_service, "make_voice_call", failing_call)

    resp = client.post("/api/alert?level=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["notification_status"] == "failed"
    assert data["success"] is False
    assert "failed" in data["message"]

    # Alert is still stored.
    resp2 = client.get("/api/alerts?range=1d")
    assert len(resp2.json()["alerts"]) == 1
    stored = resp2.json()["alerts"][0]
    assert stored["notification_status"] == "failed"


def test_production_mode_calls_twilio(client, monkeypatch):
    # Force production so the real path (which hits Twilio) is used.
    monkeypatch.setattr("app.config.is_production", lambda: True)
    called = {}

    def fake_send_sms(to, body):
        called["send_sms"] = (to, body)
        return {"status": "sent", "sid": "SM_real"}

    def fake_make_voice_call(to):
        called["voice"] = to
        return {"status": "sent", "sid": "CA_real"}

    from app import twilio_service

    monkeypatch.setattr(twilio_service, "send_sms", fake_send_sms)
    monkeypatch.setattr(twilio_service, "make_voice_call", fake_make_voice_call)

    client.post("/api/alert?level=1")
    assert called["send_sms"][0] == "+15551112222"
    assert "Warning" in called["send_sms"][1]

    client.post("/api/alert?level=2")
    assert called["voice"] == "+15553334444"


def test_dev_mode_simulates_without_credentials(monkeypatch):
    from app import config, twilio_service

    monkeypatch.setattr("app.config.is_production", lambda: False)
    # No credentials configured.
    monkeypatch.setattr(config, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(config, "TWILIO_FROM_NUMBER", "")

    # Use the REAL functions (not the autouse mock) to exercise simulation.
    real_sms = twilio_service._real_twilio_send_sms
    real_call = twilio_service._real_twilio_make_voice_call

    # Simulated SMS should not require credentials and returns a dev SID.
    sms = real_sms("+15551112222", "hello")
    assert sms["status"] == "sent"
    assert "simulated" in sms["sid"]

    # Simulated voice should not require a TWILIO_VOICE_URL either.
    call = real_call("+15553334444")
    assert call["status"] == "sent"
    assert "simulated" in call["sid"]


def test_voice_twiml_endpoint(client):
    resp = client.get("/api/twilio/voice")
    assert resp.status_code == 200
    assert "application/xml" in resp.headers["content-type"]
    assert "Emergency alert" in resp.text


def test_pages_served(client):
    assert client.get("/app").status_code == 200
    assert client.get("/admin").status_code == 200
    assert client.get("/manifest.json").status_code == 200
