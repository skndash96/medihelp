# Elderly Fall-Alert System

A complete local-development **elderly fall-detection** college project: a FastAPI
web server, SQLite database, installable **PWA** dashboard, an **admin** page, and
**Twilio** SMS / voice-call notifications. The API is designed so a future
**ESP32** pendant can post alerts over Wi-Fi.

> ⚠️ **College-project prototype — NOT a production medical/emergency system.**
> No authentication, no resilience guarantees. Do not use for real emergencies.

---

## 1. Overview

The system receives fall alerts, stores them in SQLite, and notifies a caregiver via
SMS (warning, level 1) or an automated voice call (emergency, level 2). The PWA shows
a live dashboard with history visualization; the admin page lets you trigger test
alerts.

```
Admin button / ESP32
        │
        ▼
POST /api/alert
        │
        ▼
     SQLite
        │
        ▼
  Twilio SMS / Voice
        │
        ▼
      PWA dashboard
```

## 2. Architecture

```
project/
├── app/
│   ├── main.py              # FastAPI app, CORS, error handling
│   ├── database.py          # SQLAlchemy engine + session
│   ├── models.py            # Alert ORM model
│   ├── schemas.py           # Pydantic request/response models
│   ├── config.py            # env-based configuration (loads .env)
│   ├── twilio_service.py    # all Twilio SDK calls live here
│   │
│   ├── routers/
│   │   ├── alerts.py        # /api/alert, /api/alerts, /api/stats, /api/twilio/voice
│   │   └── pages.py         # serves /app (PWA) and /admin
│   │
│   └── static/
│       ├── app/             # PWA (HTML/CSS/JS, manifest, service worker)
│       └── admin/           # admin page
├── data/alerts.db           # SQLite database (persisted)
├── tests/                   # pytest suite (Twilio mocked)
├── .env.example
├── requirements.txt
└── pyproject.toml
```

Separation kept clean: **database** (models.py) ↔ **API** (routers) ↔ **Twilio**
(twilio_service.py) ↔ **frontends** (static).

## 3. Installation

Requires Python **3.11+**.

```bash
# from the project root
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Environment variables

Copy the example file and fill in values:

```bash
cp .env.example .env
```

| Variable            | Purpose                                             |
|---------------------|-----------------------------------------------------|
| `APP_ENV`           | `development` (default) simulates SMS/voice by logging only; `production` actually calls Twilio |
| `TWILIO_ACCOUNT_SID`| Twilio account SID                                  |
| `TWILIO_AUTH_TOKEN` | Twilio auth token                                   |
| `TWILIO_FROM_NUMBER`| Your Twilio phone number, e.g. `+15551234567`       |
| `ALERT_SMS_TO`      | Caregiver phone for SMS alerts                      |
| `ALERT_CALL_TO`     | Caregiver phone for voice calls                     |
| `TWILIO_VOICE_URL`  | Public URL of the TwiML endpoint (see §8)           |

Credentials are **never hardcoded** — only read from the environment.

### Development vs production mode

Set `APP_ENV=development` (the default) for local work. In this mode
`send_sms` and `make_voice_call` are **simulated** — the intended SMS/voice
message is logged but **nothing is sent to Twilio**, and no credentials are
required. Set `APP_ENV=production` to actually send SMS/voice with Twilio.

## 5. Running locally

```bash
# convenient launcher (uvicorn underneath)
python run.py

# or run uvicorn directly
uvicorn app.main:app --reload
```

Open:
- PWA dashboard: <http://localhost:8000/app>
- Admin page: <http://localhost:8000/admin>
- API docs: <http://localhost:8000/docs>

The rest of the app works **without** Twilio configured (alerts are still stored;
notifications are recorded as `failed` if Twilio isn't set up).

## 6. API endpoints

### POST `/api/alert`
Accepts JSON **or** query parameters (for the future ESP32).

```bash
# JSON
curl -X POST http://localhost:8000/api/alert \
  -H "Content-Type: application/json" \
  -d '{"level": 1, "device_id": "pendant-01", "latitude": 10.7905, "longitude": 78.7047}'

# Query parameters (ESP32-friendly)
curl -X POST "http://localhost:8000/api/alert?level=1"
curl -X POST "http://localhost:8000/api/alert?level=2&lat=10.7905&lon=78.7047"
```

Levels: `0` = normal/test (`no notification`), `1` = warning (`SMS`), `2` = emergency (`voice call`).

Response:
```json
{
  "success": true,
  "alert_id": 42,
  "level": 2,
  "notification": "voice_call",
  "notification_status": "sent",
  "message": "OK"
}
```

### GET `/api/alerts`
`?range=1h|1d|1w|1m` returns alerts in that window, newest first.

### GET `/api/alerts/latest`
`?limit=10` returns the most recent alerts.

### GET `/api/stats`
`?range=1d` returns counts per level.

### GET/POST `/api/twilio/voice`
Returns the TwiML that tells Twilio what to say during the emergency call.

## 7. Twilio setup

1. Create a Twilio account and get a phone number.
2. Set all the env vars in `.env` (see §4).
3. For SMS and voice to work, Twilio must be able to reach your machine (see §8).

The voice message is defined in `app/routers/alerts.py` (`VOICE_EMERGENCY_MESSAGE`).
To use a **prerecorded audio file** later, swap the `<Say>` block for a `<Play>` tag —
the alert API is unchanged:

```xml
<Response>
    <Play>https://example.com/recorded-message.wav</Play>
</Response>
```

## 8. Exposing the voice endpoint (ngrok / Cloudflare Tunnel)

Twilio fetches the TwiML at `TWILIO_VOICE_URL`, so that URL must be publicly
reachable. `ngrok` or Cloudflare Tunnel lets you expose your local server:

```bash
# Terminal 1: run the server
python run.py

# Terminal 2: expose it
ngrok http 8000
```

Copy the public `https://<random>.ngrok.io` URL, then set:

```env
TWILIO_VOICE_URL=https://<random>.ngrok.io/api/twilio/voice
```

> Only the voice call needs the tunnel. Everything else (PWA, admin, alert storage,
> even SMS) works locally without one.

## 9. Installing the PWA

Open <http://localhost:8000/app> in a browser (works on mobile):

- **Mobile (Android/Chrome):** browser menu → “Add to Home screen” / “Install app”.
- **Desktop:** the install icon in the address bar, or Chrome menu → “Install”.

Once installed it opens fullscreen and the shell loads offline (via the service
worker). Live alert data requires a connection.

## 10. Testing from the admin page

1. Open <http://localhost:8000/admin>.
2. Tap **SEND WARNING (LEVEL 1)** → triggers `POST /api/alert?level=1` and sends an SMS.
3. Tap **SEND EMERGENCY (LEVEL 2)** → triggers `POST /api/alert?level=2` and a voice call.
4. The result and the most recent alerts appear below the buttons.
5. Watch the dashboard update at `/app`.

## 11. Example future ESP32 request

The API is designed for an ESP32 with an MPU6050 + GPS to post over Wi-Fi:

```cpp
// (future firmware pseudocode)
http.begin(http, "http://<server-ip>:8000/api/alert?level=1&lat=10.7905&lon=78.7047");
int code = http.POST("");
```

Payload fields (`device_id`, `latitude`, `longitude`) are optional and easy to
extend with future fields like `battery`, `heart_rate`, `activity`.

## 12. Automated tests

Twilio is mocked — tests never send real SMS/voice.

```bash
pytest -q
```

Covered: level 0/1/2 alerts, invalid level, invalid coordinates, persistence,
range filtering, latest, stats, Twilio-failure handling, TwiML endpoint, page serving.

## 13. Known limitations

- **No authentication** on `/admin` — local prototype only, not production-secure.
- Twilio calls/SMS depend on live credentials and a reachable `TWILIO_VOICE_URL`.
- Not a real medical alerting system — informational only.
- CORS is wide-open for local convenience.
- Real-time offline alert sync is intentionally **not** implemented.
