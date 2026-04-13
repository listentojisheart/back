"""
Database session management.
Uses sync SQLAlchemy for simplicity; FastAPI handles concurrency fine with thread pool.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


# Railway provides DATABASE_URL starting with postgres://, SQLAlchemy 2.0 needs postgresql://
def _normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


engine = create_engine(
    _normalize_db_url(settings.DATABASE_URL),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a db session, ensures close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
