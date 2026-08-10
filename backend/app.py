"""
AP — Authenticity & Provenance Console — backend API.

Combines two toolsets behind one FastAPI app:

  1. Media forensics   — POST /api/analyze/{image,video,audio}
     (frequency/ELA/noise/temporal/pitch heuristics — see detectors/)

  2. Threat watchdog    — POST /api/scan, POST /api/chat
     (breach / phishing / exposed-secrets / exposed-infra checks — see checkers/)

Run with:
    uvicorn app:app --reload --port 8000

Then open http://localhost:8000 — this app serves the frontend directly.
"""

import os
import re
import json
import shutil
import tempfile
import time
import datetime
import asyncio
from typing import Optional

import cv2
from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ---- media forensics detectors ----
from detectors.image_detector import analyze_image
from detectors.video_detector import analyze_video
from detectors.audio_detector import analyze_audio

# ---- threat-intel checkers ----
from checkers import breach, phishing, github_secrets, shodan_check, ai_summary
from checkers.mock import mock_ransomware_mentions

# ---- login + case history ----
from database import init_db, SessionLocal
from models import User, Case
from auth import verify_google_token, issue_session_token, get_current_user, get_current_user_optional

app = FastAPI(title="AP — Authenticity & Provenance Console API", version="1.0")

init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
# Shared
# =====================================================================


@app.get("/api/health")
def health():
    return {"status": "ok"}


# =====================================================================
# 0. Login (Sign in with Google) + case history
# =====================================================================


class GoogleAuthRequest(BaseModel):
    credential: str


def _user_public(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}


@app.get("/api/config")
@app.get("/api/auth/config")
def get_config():
    """Public config the frontend needs before it can render the login button."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    return {"enabled": bool(client_id), "google_client_id": client_id}


@app.post("/api/auth/google")
def auth_google(req: GoogleAuthRequest):
    payload = verify_google_token(req.credential)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.google_sub == payload["sub"]).first()
        now = datetime.datetime.utcnow()
        if user is None:
            user = User(
                google_sub=payload["sub"],
                email=payload.get("email", ""),
                name=payload.get("name", ""),
                picture=payload.get("picture", ""),
                created_at=now,
                last_login_at=now,
            )
            db.add(user)
        else:
            user.email = payload.get("email", user.email)
            user.name = payload.get("name", user.name)
            user.picture = payload.get("picture", user.picture)
            user.last_login_at = now
        db.commit()
        db.refresh(user)
        token = issue_session_token(user)
        return {"token": token, "user": _user_public(user)}
    finally:
        db.close()


@app.get("/api/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    return _user_public(user)


@app.post("/api/auth/logout")
def auth_logout():
    return {"status": "ok"}


def _save_case(user: Optional[User], case_type: str, label: str, verdict, confidence, result: dict):
    """Best-effort: persist a case to history for a signed-in user. No-op if not logged in."""
    if user is None:
        return
    db = SessionLocal()
    try:
        db.add(Case(
            user_id=user.id,
            case_type=case_type,
            label=(label or "")[:512],
            verdict=str(verdict) if verdict is not None else None,
            confidence=int(confidence) if confidence is not None else None,
            result_json=json.dumps(result),
        ))
        db.commit()
    finally:
        db.close()


@app.get("/api/history")
@app.get("/api/cases")
def get_history(case_type: Optional[str] = None, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        q = db.query(Case).filter(Case.user_id == user.id)
        if case_type:
            q = q.filter(Case.case_type == case_type)
        cases = q.order_by(Case.created_at.desc()).limit(200).all()
        return [
            {
                "id": c.id,
                "case_type": c.case_type,
                "label": c.label,
                "verdict": c.verdict,
                "confidence": c.confidence,
                "created_at": c.created_at.isoformat() + "Z",
            }
            for c in cases
        ]
    finally:
        db.close()


@app.get("/api/history/{case_id}")
@app.get("/api/cases/{case_id}")
def get_case_detail(case_id: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
        if case is None:
            raise HTTPException(404, "Case not found")
        return {
            "id": case.id,
            "case_type": case.case_type,
            "label": case.label,
            "verdict": case.verdict,
            "confidence": case.confidence,
            "created_at": case.created_at.isoformat() + "Z",
            "result": json.loads(case.result_json),
        }
    finally:
        db.close()


@app.delete("/api/history/{case_id}")
@app.delete("/api/cases/{case_id}")
def delete_case(case_id: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
        if case is None:
            raise HTTPException(404, "Case not found")
        db.delete(case)
        db.commit()
        return {"status": "deleted", "id": case_id}
    finally:
        db.close()


# =====================================================================
# 1. Media forensics — image / video / audio manipulation analysis
# =====================================================================

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
MAX_FILE_MB = 80


def _verdict(confidence):
    if confidence >= 38:
        return "likely_manipulated"
    if confidence <= 25:
        return "likely_authentic"
    return "uncertain"


def _save_temp(upload: UploadFile, allowed_exts):
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(allowed_exts)}")

    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    size = 0
    with os.fdopen(fd, "wb") as out:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_MB * 1024 * 1024:
                out.close()
                os.remove(tmp_path)
                raise HTTPException(413, f"File exceeds {MAX_FILE_MB}MB limit.")
            out.write(chunk)
    return tmp_path


@app.post("/api/analyze/image")
async def analyze_image_endpoint(file: UploadFile = File(...), user: Optional[User] = Depends(get_current_user_optional)):
    tmp_path = _save_temp(file, IMAGE_EXTS)
    try:
        start = time.time()
        img = cv2.imread(tmp_path)
        if img is None:
            raise HTTPException(400, "Could not decode image file.")
        with open(tmp_path, "rb") as f:
            raw_bytes = f.read()
        result = analyze_image(img, raw_bytes=raw_bytes)
        result["verdict"] = _verdict(result["manipulation_confidence"])
        result["processing_ms"] = round((time.time() - start) * 1000, 1)
        result["media_type"] = "image"
        _save_case(user, "image", file.filename, result["verdict"], result["manipulation_confidence"], result)
        return result
    finally:
        os.remove(tmp_path)


@app.post("/api/analyze/video")
async def analyze_video_endpoint(file: UploadFile = File(...), user: Optional[User] = Depends(get_current_user_optional)):
    tmp_path = _save_temp(file, VIDEO_EXTS)
    try:
        start = time.time()
        result = analyze_video(tmp_path)
        if "error" in result:
            raise HTTPException(400, result["error"])
        result["verdict"] = _verdict(result["manipulation_confidence"])
        result["processing_ms"] = round((time.time() - start) * 1000, 1)
        result["media_type"] = "video"
        _save_case(user, "video", file.filename, result["verdict"], result["manipulation_confidence"], result)
        return result
    finally:
        os.remove(tmp_path)


@app.post("/api/analyze/audio")
async def analyze_audio_endpoint(file: UploadFile = File(...), user: Optional[User] = Depends(get_current_user_optional)):
    tmp_path = _save_temp(file, AUDIO_EXTS)
    try:
        start = time.time()
        result = analyze_audio(tmp_path)
        if "error" in result:
            raise HTTPException(400, result["error"])
        result["verdict"] = _verdict(result["manipulation_confidence"])
        result["processing_ms"] = round((time.time() - start) * 1000, 1)
        result["media_type"] = "audio"
        _save_case(user, "audio", file.filename, result["verdict"], result["manipulation_confidence"], result)
        return result
    finally:
        os.remove(tmp_path)


# =====================================================================
# 2. Threat watchdog — domain / email exposure scan + chat explainer
# =====================================================================

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ScanRequest(BaseModel):
    target: str


class ChatRequest(BaseModel):
    question: str
    scan: dict


def extract_domain(target: str) -> str:
    if EMAIL_RE.match(target):
        return target.split("@", 1)[1]
    return target.replace("https://", "").replace("http://", "").split("/")[0]


def compute_risk(scan: dict) -> str:
    score = 0
    score += len(scan["breaches"]) * 2
    score += len(scan["phishing_domains"]) * 2
    score += len(scan["github_secrets"]) * 3
    score += len(scan["exposed_infra"]) * 2
    score += len(scan["ransomware_mentions"]) * 5

    if score == 0:
        return "LOW"
    if score <= 4:
        return "LOW"
    if score <= 10:
        return "MEDIUM"
    if score <= 18:
        return "HIGH"
    return "CRITICAL"


def build_actions(scan: dict) -> list[str]:
    actions = []
    if scan["breaches"]:
        actions.append("Force a password reset for all accounts tied to this target")
        actions.append("Enable multi-factor authentication (MFA) everywhere it isn't already on")
    if scan["github_secrets"]:
        actions.append("Rotate every exposed API key / credential and purge it from git history")
    if scan["phishing_domains"]:
        actions.append("Report look-alike domains to their registrar and warn employees/customers")
    if scan["exposed_infra"]:
        actions.append("Close or patch the exposed services found on public scan engines")
    if scan["ransomware_mentions"]:
        actions.append("Engage incident response immediately — a ransomware group has referenced this target")
    if not actions:
        actions.append("No urgent action required — keep recurring monitoring on")
    return actions


@app.post("/api/scan")
async def scan(req: ScanRequest, user: Optional[User] = Depends(get_current_user_optional)):
    target = req.target.strip()
    if not target:
        raise HTTPException(400, "target is required")

    is_email = bool(EMAIL_RE.match(target))
    domain = extract_domain(target)

    breach_result, phish_domains, phish_rep, gh_result, shodan_result = await asyncio.gather(
        breach.check_breaches(target, is_email),
        phishing.check_lookalike_domains(domain),
        phishing.check_domain_reputation(domain),
        github_secrets.check_github_secrets(domain),
        shodan_check.check_exposed_infra(domain),
    )

    scan_result = {
        "target": target,
        "domain": domain,
        "is_email": is_email,
        "breaches": breach_result["breaches"],
        "breaches_source": breach_result["source"],
        "phishing_domains": phish_domains["domains"],
        "phishing_domains_source": phish_domains["source"],
        "domain_reputation": phish_rep,
        "github_secrets": gh_result["hits"],
        "github_secrets_source": gh_result["source"],
        "exposed_infra": shodan_result["exposures"],
        "exposed_infra_source": shodan_result["source"],
        "ransomware_mentions": mock_ransomware_mentions(target),
        "ransomware_mentions_source": "mock",
    }
    scan_result["risk_level"] = compute_risk(scan_result)
    scan_result["recommended_actions"] = build_actions(scan_result)

    ai_result = await ai_summary.summarize(target, scan_result)
    scan_result["ai_summary"] = ai_result["summary"]
    scan_result["ai_summary_source"] = ai_result["source"]

    _save_case(user, "intel", target, scan_result["risk_level"], None, scan_result)

    return scan_result


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(400, "question is required")
    result = await ai_summary.explain_threat(req.question, req.scan)
    return result


# =====================================================================
# Serve the frontend (static build) if present, so `uvicorn app:app`
# alone is enough to demo the whole platform.
# =====================================================================
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(FRONTEND_DIR):
    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
