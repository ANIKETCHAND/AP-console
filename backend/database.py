"""
Database persistence layer for AP — Authenticity & Provenance Console.
Uses in-memory SQLite by default for zero-setup execution, or point
`DATABASE_URL` at PostgreSQL/MySQL for persistent storage.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

raw_db = os.environ.get("DATABASE_URL", "").strip()

# Always use in-memory SQLite unless a real external PostgreSQL/MySQL URL is provided
if not raw_db or raw_db.startswith("sqlite") or "ap_console" in raw_db:
    DATABASE_URL = "sqlite:///:memory:"
else:
    DATABASE_URL = raw_db

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
pool_kwargs = {"poolclass": StaticPool} if DATABASE_URL == "sqlite:///:memory:" else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, **pool_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create all database tables on engine startup."""
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
