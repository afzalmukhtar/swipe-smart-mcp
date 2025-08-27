from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _resolve_db_path() -> str:
    # Place finance.db at the repo root (two levels up from this file: src/finance_mcp)
    repo_root = Path(__file__).resolve().parents[2]
    db_path = repo_root / "finance.db"
    return f"sqlite:///{db_path}"


ENGINE = create_engine(
    _resolve_db_path(), echo=False, future=True
)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)


def get_db_session() -> Generator[Session, None, None]:
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    # Local import to avoid circulars
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=ENGINE)


