"""Async engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from classtrack.core.config import get_settings


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: object, _record: object) -> None:
    """Turn on foreign-key enforcement for SQLite.

    SQLite ignores foreign keys unless asked, so ``ON DELETE CASCADE`` silently
    does nothing and re-ingesting a routine version leaves its old rows behind.
    Registered on ``Engine`` so every engine gets it, tests included.
    """
    cls = type(dbapi_connection)
    if "sqlite" in f"{cls.__module__}.{cls.__name__}".lower():
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs: dict[str, object] = {"echo": settings.db_echo, "future": True}
        if settings.database_url.startswith("sqlite"):
            # SQLite has no pool to tune and needs FK enforcement turned on.
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs |= {"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True}
        _engine = create_async_engine(settings.database_url, **kwargs)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False, autoflush=False
        )
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session that rolls back on error."""
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
