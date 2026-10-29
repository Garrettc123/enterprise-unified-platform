"""Database configuration and session management with SQLAlchemy 2.x async support."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

Base = declarative_base()
engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_database_url() -> str:
    """Resolve the database URL from the secret manager or environment variables."""
    secrets_provider = os.getenv("SECRETS_PROVIDER")
    secret_name = os.getenv("DB_SECRET_NAME")

    if secrets_provider and secret_name:
        try:
            # Keep the optional adapter lazy so its absence does not break module import.
            from backend.secrets import get_database_url_from_secrets

            secret_url = await get_database_url_from_secrets(
                provider=secrets_provider,
                secret_name=secret_name,
            )
            if secret_url:
                return _async_database_url(secret_url)
        except Exception:
            # Fall back without logging or exposing secret values.
            pass

    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return _async_database_url(database_url)

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME", "enterprise_db")
    username = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"


def _async_database_url(url: str) -> str:
    """Normalize PostgreSQL URL schemes and SSL parameters for the asyncpg driver."""
    parsed = urlsplit(url)
    if parsed.scheme in {"postgres", "postgresql"}:
        parsed = parsed._replace(scheme="postgresql+asyncpg")

    if parsed.scheme != "postgresql+asyncpg":
        return url

    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    has_ssl = any(key == "ssl" for key, _ in query_items)
    normalized_query: list[tuple[str, str]] = []
    for key, value in query_items:
        if key == "sslmode":
            if not has_ssl:
                normalized_query.append(("ssl", value))
            continue
        normalized_query.append((key, value))

    return urlunsplit(parsed._replace(query=urlencode(normalized_query, doseq=True)))


async def init_db() -> None:
    """Initialize database engine and session factory."""
    global engine, async_session_factory

    database_url = await get_database_url()
    engine_kwargs: dict[str, Any] = {
        "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
        "pool_pre_ping": True,
        "connect_args": {
            "server_settings": {"application_name": "enterprise-platform"},
            "timeout": 30,
        },
    }
    if os.getenv("DB_POOL_DISABLE") == "true":
        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
        engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        engine_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    engine = create_async_engine(database_url, **engine_kwargs)
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def receive_connect(dbapi_conn: Any, connection_record: Any) -> None:
        """Configure statement timeout on connect."""
        with dbapi_conn.cursor() as cursor:
            cursor.execute("SET statement_timeout = '30s'")


async def close_db() -> None:
    """Close database connections and dispose the engine."""
    global engine, async_session_factory
    if engine:
        await engine.dispose()
        engine = None
    async_session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a managed async database session."""
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all tables; use Alembic migrations for production."""
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all tables and delete their data."""
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
