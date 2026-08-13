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

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, declarative_base
    from sqlalchemy.pool import StaticPool
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

if HAS_SQLALCHEMY:
    is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    if is_serverless:
        DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        DB_PATH = os.path.join(os.path.dirname(__file__), "ap_console.db")
        DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")
        _connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
        engine = create_engine(DATABASE_URL, connect_args=_connect_args)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
else:
    engine = None
    SessionLocal = None
    Base = None


def init_db():
    if not HAS_SQLALCHEMY or Base is None or engine is None:
        return
    try:
        try:
            from . import models  # noqa: F401
        except ImportError:
            import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print("Database init notice:", e)
