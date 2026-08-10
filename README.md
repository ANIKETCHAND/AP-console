# AP — Authenticity & Provenance Console

A full-stack investigative console that combines two toolsets in one app,
under one FastAPI backend and one dark "forensics lab" UI:

1. **Media forensics** (from the original AP console) — upload an image,
   video, or voice clip (or run a live webcam scan) and get a
   manipulation-confidence score with a signal-by-signal breakdown.
2. **Threat intel / exposure watchdog** (from DarkWeb Watchdog) — enter a
   company domain or email and check leaked credentials, phishing
   look-alike domains, exposed secrets on GitHub, exposed infrastructure,
   and ransomware leak-site mentions, with an AI-generated risk summary,
   action list, and a follow-up chat box.
3. **Login (Sign in with Google) + case history** — a login page gates
   the console; every analysis and scan a signed-in investigator runs is
   saved to a database and reopenable later from the **History** tab.

```
AP-console/
├── backend/
│   ├── app.py                    single FastAPI server, both APIs, login + history
│   ├── database.py                SQLAlchemy engine/session (SQLite by default)
│   ├── models.py                  User + Case (history) tables
│   ├── auth.py                    Google ID-token verification + session JWTs
│   ├── requirements.txt
│   ├── .env.example               optional keys for live threat-intel data + login/DB config
│   ├── ap_console.db               (created on first run) local SQLite database
│   ├── detectors/                 media forensics (image/video/audio)
│   │   ├── image_detector.py      FFT / ELA / noise / symmetry analysis
│   │   ├── video_detector.py      frame sampling + blink-rate + temporal
│   │   └── audio_detector.py      pitch / spectral / MFCC voice analysis
│   └── checkers/                  threat-intel exposure checks
│       ├── breach.py               HaveIBeenPwned (live) / mock
│       ├── phishing.py             VirusTotal reputation (live) + lookalikes (mock)
│       ├── github_secrets.py       GitHub code search (live, no key required)
│       ├── shodan_check.py         Shodan (live) / mock
│       ├── ai_summary.py           OpenAI summary + chatbot (live) / template
│       └── mock.py                 deterministic mock-data generators
├── frontend/
│   ├── index.html                 login page + 6 exhibits: Image / Video / Voice / Live feed / Threat intel / History
│   ├── style.css                  shared "forensics lab" design system
│   └── script.js                  login, upload UI, gauge, webcam loop, intel scan + chat, history
└── README.md
```

## Run it

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # then fill in GOOGLE_CLIENT_ID (see "Login" below)
uvicorn app:app --reload --port 8000
```

Then open **http://localhost:8000** — FastAPI serves the frontend directly,
so there's nothing else to start. A local SQLite file (`backend/ap_console.db`)
is created automatically on first run to store users and case history.

## Login (Sign in with Google)

The console is gated by a login page. To enable it:

1. Go to [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
   and create an **OAuth 2.0 Client ID** of type "Web application".
2. Under "Authorized JavaScript origins", add the URL you'll open the app
   from — e.g. `http://localhost:8000`. No redirect URI is needed.
3. Copy the client ID into `GOOGLE_CLIENT_ID` in `backend/.env`.
4. Also set `JWT_SECRET` in `backend/.env` to any long random string —
   this signs the app's own login sessions (separate from Google's token).

Without a `GOOGLE_CLIENT_ID`, the login page loads but shows a message
that Google Sign-In isn't configured yet, instead of the sign-in button.

Every media analysis and threat-intel scan a signed-in user runs is saved
to the database and viewable from the **History** tab, filterable by
type (image / video / voice / threat intel). Clicking a case reopens its
full result. History is per-user — nobody sees anyone else's cases.

## Media forensics — what's real

**This is not a trained deep-learning deepfake classifier.** Each detector
implements real, published forensic signal-processing techniques (FFT
artifact analysis, error-level analysis, sensor-noise consistency,
blink-rate/temporal analysis, pitch/MFCC analysis) and fuses them into a
confidence score. Treat scores as investigative signal, not forensic proof.
See the detector docstrings for references, and the original AP README
section on upgrading to a trained model (e.g. an XceptionNet/EfficientNet
fine-tuned on FaceForensics++/DFDC) if you want production-grade accuracy.

## Threat intel — what's real vs. mock

**Runs fully in demo mode with zero API keys.** Every checker has a
deterministic mock fallback, so the console is fully demoable out of the
box. Every finding in the UI is tagged with its source (`live` or `mock`).

| Checker | Live when... | Free? |
|---|---|---|
| Leaked credentials | `HIBP_API_KEY` set (email targets only) | No — HIBP is ~$3.95/mo |
| Domain reputation | `VIRUSTOTAL_API_KEY` set | Yes, free tier |
| Exposed GitHub secrets | Always attempts live GitHub code search | Yes, no key required (rate-limited; add `GITHUB_TOKEN` for a higher limit) |
| Exposed infrastructure | `SHODAN_API_KEY` set | Free trial available |
| Phishing look-alike domains | Always mock | No free real-time registry API exists |
| Ransomware leak-site mentions | Always mock | No free API exists |
| AI summary + chatbot | `OPENAI_API_KEY` set | No — falls back to a rule-based template |

Add keys to `backend/.env` (copy from `.env.example`) — none are required
to run and demo the console.

## API reference

**Login + history**

| Method | Path                | Body                     | Returns |
|--------|---------------------|---------------------------|---------|
| GET    | `/api/config`        | —                          | `{google_client_id}` — public config for the login page |
| POST   | `/api/auth/google`   | `{"credential": "<Google ID token>"}` | `{token, user}` — app session JWT + profile |
| GET    | `/api/auth/me`       | — (Bearer token)           | current user's profile |
| GET    | `/api/history`       | — (Bearer token, optional `?case_type=`) | list of the user's past cases (id, type, label, verdict, date) |
| GET    | `/api/history/{id}`  | — (Bearer token)           | full stored result for one past case |

**Media forensics**

| Method | Path                  | Body                      | Returns |
|--------|-----------------------|---------------------------|---------|
| POST   | `/api/analyze/image`   | multipart `file` (+ optional Bearer token) | confidence + signal breakdown |
| POST   | `/api/analyze/video`   | multipart `file` (+ optional Bearer token) | confidence + signal breakdown + per-frame timeline |
| POST   | `/api/analyze/audio`   | multipart `file` (+ optional Bearer token) | confidence + signal breakdown |

Max upload size: 80MB (`MAX_FILE_MB` in `app.py`). When a valid Bearer
token is sent, the result is also saved to that user's case history.

**Threat intel**

| Method | Path         | Body                                  | Returns |
|--------|--------------|----------------------------------------|---------|
| POST   | `/api/scan`   | `{"target": "domain-or-email"}` (+ optional Bearer token) | breaches, phishing domains, exposed secrets, exposed infra, ransomware mentions, risk level, recommended actions, AI summary |
| POST   | `/api/chat`   | `{"question": "...", "scan": {...}}`   | plain-language answer about a specific scan result |

**Shared**

| Method | Path          | Returns |
|--------|---------------|---------|
| GET    | `/api/health` | `{status: "ok"}` |

## Live webcam mode

The "Live feed" tab captures a JPEG frame from `getUserMedia` every 2.5s and
posts it to `/api/analyze/image` — same pipeline as a still-image upload,
just looped client-side. Nothing is stored server-side; each frame is
analyzed from an in-memory temp file and deleted immediately after.

## Known limitations

- Media-forensics heuristics can be fooled by clean recompression, only
  work well when a face is detected for the symmetry/blink signals, and
  haven't been validated against a labeled benchmark.
- Phishing look-alike domains and ransomware leak-site mentions have no
  free real-time API and stay mock-driven, clearly labeled as such.
- Results only persist to history for signed-in users; anonymous use
  (or a request sent without a valid session token) is still fully
  stateless, same as before. The live webcam loop never persists frames
  or results, signed in or not — see "Live webcam mode" above.
- History storage is a local SQLite file by default (fine for a single
  demo/dev instance); point `DATABASE_URL` at Postgres/MySQL for anything
  multi-instance or production-facing.
