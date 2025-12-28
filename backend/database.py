"""Database configuration and session management with SQLAlchemy 2.x async support."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from backend.secrets import get_database_url_from_secrets

# Create declarative base for models
Base = declarative_base()

# Global engine and session factory
engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_database_url() -> str:
    """Get database URL from secrets manager or environment variables.

    Returns:
        Database URL string for async SQLAlchemy
    """
    try:
        # Try to get from secrets manager
        secrets_provider = os.getenv("SECRETS_PROVIDER")
        secret_name = os.getenv("DB_SECRET_NAME")

        if secrets_provider and secret_name:
            return await get_database_url_from_secrets(
                provider=secrets_provider,
                secret_name=secret_name,
            )
    except Exception:
        # Fallback to environment variables
        pass

    # Use environment variables
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME", "enterprise_db")
    username = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")

    return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"


async def init_db() -> None:
    """Initialize database engine and session factory."""
    global engine, async_session_factory

    database_url = await get_database_url()

    # Create async engine with proper pool configuration
    engine = create_async_engine(
        database_url,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        pool_pre_ping=True,  # Enable connection health checks
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
        poolclass=NullPool if os.getenv("DB_POOL_DISABLE") == "true" else None,
        connect_args={
            "server_settings": {"application_name": "enterprise-platform"},
            "timeout": 30,
        },
    )

    # Create session factory
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Set up event listeners for connection pool
    @event.listens_for(engine.sync_engine, "connect")
    def receive_connect(dbapi_conn: Any, connection_record: Any) -> None:
        """Configure connection on connect."""
        # Set statement timeout to prevent long-running queries
        with dbapi_conn.cursor() as cursor:
            cursor.execute("SET statement_timeout = '30s'")


async def close_db() -> None:
    """Close database connections and dispose engine."""
    global engine
    if engine:
        await engine.dispose()
        engine = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get async database session.

    Yields:
        AsyncSession for database operations

    Example:
        ```python
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
        ```
    """
    if async_session_factory is None:
        msg = "Database not initialized. Call init_db() first."
        raise RuntimeError(msg)

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
    """Create all database tables.

    Note: For production, use Alembic migrations instead.
    """
    if engine is None:
        msg = "Database not initialized. Call init_db() first."
        raise RuntimeError(msg)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all database tables.

    Warning: This will delete all data!
    """
    if engine is None:
        msg = "Database not initialized. Call init_db() first."
        raise RuntimeError(msg)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
