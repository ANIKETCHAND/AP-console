"""
SQLite persistence layer for AP — Authenticity & Provenance Console.

Stores registered users (created on first Google Sign-In) and a history
of every case a signed-in user runs — media-forensics analyses and
threat-intel scans — so the "History" tab can show them their own past
work. Zero setup required: it's a single SQLite file created next to
this module the first time the server starts. Point `DATABASE_URL` at a
Postgres/MySQL URL instead if you want a shared server-side database.
"""

import os
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

IS_VERCEL = bool(
    os.environ.get("VERCEL") or 
    os.environ.get("VERCEL_ENV") or 
    os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or 
    os.environ.get("LAMBDA_TASK_ROOT") or
    not os.access(os.path.dirname(__file__), os.W_OK)
)

if IS_VERCEL:
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool if DATABASE_URL.startswith("sqlite") else None
    )
else:
    _db_dir = os.path.dirname(__file__)
    try:
        _test_path = os.path.join(_db_dir, ".write_test")
        with open(_test_path, "w") as f:
            f.write("1")
        os.remove(_test_path)
    except Exception:
        _db_dir = tempfile.gettempdir()

    DB_PATH = os.path.abspath(os.path.join(_db_dir, "ap_console.db"))
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")
    _connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create all tables if they don't exist yet. Safe to call every startup."""
    global engine, SessionLocal
    import models  # noqa: F401 — import so Base knows about them before create_all
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        # Fail-safe for read-only serverless environments: fallback to in-memory SQLite
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
