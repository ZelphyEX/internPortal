"""Database engine + session factory.

`get_db()` (the FastAPI dependency) lives in `app.core.deps`.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # drop dead connections instead of erroring
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,  # keep attributes usable after commit (return in responses)
)
