"""
Database persistence layer for AP — Authenticity & Provenance Console.
Uses in-memory SQLite by default for zero-setup execution, or point
`DATABASE_URL` at PostgreSQL/MySQL for persistent storage.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///:memory:")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
pool_kwargs = {"poolclass": StaticPool} if DATABASE_URL == "sqlite:///:memory:" else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, **pool_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create all database tables on engine startup."""
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
