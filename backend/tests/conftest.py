import os
import sys

# The repository contains backend/secrets, which can shadow Python's stdlib
# `secrets` module when pytest imports FastAPI/Starlette. Load the stdlib
# module first, then restore the backend path for application imports.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR in sys.path:
    sys.path.remove(_BACKEND_DIR)
import secrets as _stdlib_secrets  # noqa: F401,E402
sys.path.insert(0, _BACKEND_DIR)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.main import app
from backend.database import get_db
from backend.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_db():
    """Set up in-memory test database for every test"""
    import asyncio

    async def _setup():
        engine = create_async_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        return engine

    loop = asyncio.new_event_loop()
    engine = loop.run_until_complete(_setup())

    yield

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    loop.run_until_complete(_teardown())
    loop.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)
