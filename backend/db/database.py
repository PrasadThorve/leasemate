"""Database connection setup: SQLite + SQLAlchemy 2.0.

Everything that talks to the database imports `SessionLocal` from here.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'leasemate.db').as_posix()}"

# Tests can point DATABASE_URL at a throwaway database instead of the real one.
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    # SQLite only allows one thread per connection by default; FastAPI uses several.
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class that every table model inherits from."""


def init_db(drop_existing: bool = False) -> None:
    """Create all tables. With drop_existing=True, delete them first."""
    from db import models  # noqa: F401  (importing the models registers the tables)

    if drop_existing:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
