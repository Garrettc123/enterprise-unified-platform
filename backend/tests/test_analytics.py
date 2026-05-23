import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.main import app
from backend.database import get_db
from backend.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_db():
    """Set up test database for each test"""
    import asyncio

    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield session_factory

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_teardown())
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def _register_and_login(client):
    """Helper to register a user and return access token"""
    client.post(
        "/register",
        json={
            "username": "adminuser",
            "email": "admin@example.com",
            "password": "adminpass123",
            "full_name": "Admin User",
        },
    )
    resp = client.post(
        "/login",
        data={"username": "adminuser", "password": "adminpass123"},
    )
    return resp.json()["access_token"]


def _make_superuser(session_factory):
    """Helper to promote a user to superuser"""
    import asyncio
    from backend.models import User

    async def _promote():
        async with session_factory() as session:
            result = await session.execute(
                select(User).where(User.username == "adminuser")
            )
            user = result.scalar_one()
            user.is_superuser = True
            await session.commit()

    asyncio.run(_promote())


def test_admin_overview_returns_metrics(client, setup_test_db):
    """Test admin overview endpoint returns expected metric fields"""
    token = _register_and_login(client)
    _make_superuser(setup_test_db)

    response = client.get(
        "/api/analytics/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all expected keys exist
    assert "total_users" in data
    assert "active_users" in data
    assert "total_organizations" in data
    assert "total_projects" in data
    assert "total_tasks" in data
    assert "completed_tasks" in data
    assert "completion_rate" in data
    assert "new_users_last_week" in data
    assert "new_projects_last_week" in data
    assert "project_status_breakdown" in data
    assert "task_priority_breakdown" in data
    assert "task_status_breakdown" in data
    assert "recent_activity" in data

    # Verify types
    assert isinstance(data["total_users"], int)
    assert isinstance(data["total_projects"], int)
    assert isinstance(data["completion_rate"], (int, float))
    assert isinstance(data["project_status_breakdown"], list)
    assert isinstance(data["task_priority_breakdown"], list)
    assert isinstance(data["task_status_breakdown"], list)
    assert isinstance(data["recent_activity"], list)


def test_admin_overview_has_registered_user(client, setup_test_db):
    """Test admin overview counts the registered user"""
    token = _register_and_login(client)
    _make_superuser(setup_test_db)

    response = client.get(
        "/api/analytics/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    # At least 1 user (the one we just registered)
    assert data["total_users"] >= 1
    assert data["active_users"] >= 1
    assert data["new_users_last_week"] >= 1


def test_admin_overview_requires_auth(client):
    """Test admin overview requires authentication"""
    response = client.get("/api/analytics/admin/overview")
    assert response.status_code in (401, 403, 422)


def test_admin_overview_requires_superuser(client, setup_test_db):
    """Test admin overview requires superuser privileges"""
    token = _register_and_login(client)
    # Don't promote to superuser

    response = client.get(
        "/api/analytics/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
