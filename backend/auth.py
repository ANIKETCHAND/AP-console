"""
Login — Sign in with Google.

Flow:
  1. Frontend loads Google Identity Services and shows the "Sign in with
     Google" button (client id comes from GET /api/config).
  2. Once the person picks an account, Google hands the frontend a
     signed ID token ("credential").
  3. Frontend POSTs it to /api/auth/google. This module verifies it was
     really issued by Google for *this* app, upserts a local User row,
     and issues the app's own short-lived session JWT.
  4. The frontend attaches that JWT as `Authorization: Bearer <token>`
     on every later request; get_current_user[_optional] below decode
     it back into a User row.
"""

import os
import datetime
from typing import Optional

import jwt
from fastapi import Header, HTTPException
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from database import SessionLocal
from models import User

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGO = "HS256"
JWT_EXPIRE_DAYS = 7

_google_request = google_requests.Request()


def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token and return its decoded payload (email, name, sub, ...)."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            500,
            "GOOGLE_CLIENT_ID is not configured on the server — "
            "add it to backend/.env, see README.",
        )
    try:
        payload = google_id_token.verify_oauth2_token(
            credential, _google_request, GOOGLE_CLIENT_ID
        )
    except ValueError as e:
        raise HTTPException(401, f"Invalid Google credential: {e}")

    if payload.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "Invalid token issuer.")
    return payload


def issue_session_token(user: User) -> str:
    """Mint this app's own session JWT for an already-verified user."""
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid or expired session: {e}")


def get_current_user_optional(authorization: Optional[str] = Header(default=None)) -> Optional[User]:
    """FastAPI dependency: attach the signed-in User if present, else None (doesn't reject)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        data = _decode(token)
    except HTTPException:
        return None
    db = SessionLocal()
    try:
        return db.get(User, int(data["sub"]))
    finally:
        db.close()


def get_current_user(authorization: Optional[str] = Header(default=None)) -> User:
    """FastAPI dependency: require a valid session, or reject with 401."""
    user = get_current_user_optional(authorization)
    if user is None:
        raise HTTPException(401, "Sign in required.")
    return user
