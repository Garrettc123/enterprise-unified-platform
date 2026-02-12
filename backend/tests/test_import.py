import pytest
import asyncio
import csv
import json
from io import StringIO, BytesIO
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.main import app
from backend.database import get_db
from backend.models import Base, User, Organization, Project

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_db():
    """Create test database and seed data."""

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

    # Seed an organization and project for import tests
    async def _seed():
        async with session_factory() as session:
            from backend.security import get_password_hash

            user = User(
                username="importer",
                email="importer@example.com",
                hashed_password=get_password_hash("testpass123"),
                full_name="Import User",
            )
            session.add(user)
            await session.flush()

            org = Organization(
                name="Test Org",
                slug="test-org",
                description="Org for testing imports",
            )
            session.add(org)
            await session.flush()

            project = Project(
                name="Test Project",
                organization_id=org.id,
                created_by=user.id,
                status="active",
            )
            session.add(project)
            await session.commit()

    asyncio.run(_seed())

    yield session_factory

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_teardown())

    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    """Get auth token for the seeded user."""
    response = client.post(
        "/login",
        data={"username": "importer", "password": "testpass123"},
    )
    return response.json()["access_token"]


def _make_csv(headers, rows):
    """Helper to build CSV bytes from headers and rows."""
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


# ── Project CSV import ──────────────────────────────────────────────


def test_import_projects_csv(client, auth_token):
    csv_data = _make_csv(
        ["Name", "Description", "Status", "Priority", "Budget"],
        [
            ["Alpha", "First project", "active", "high", "10000"],
            ["Beta", "Second project", "completed", "low", ""],
        ],
    )
    response = client.post(
        "/api/import/projects/csv?organization_id=1",
        files={"file": ("projects.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 2
    assert body["errors"] == []
    assert body["total_rows"] == 2


def test_import_projects_csv_validation_errors(client, auth_token):
    csv_data = _make_csv(
        ["Name", "Description", "Status", "Priority", "Budget"],
        [
            ["", "No name", "active", "medium", ""],
            ["Good", "Valid row", "active", "medium", "500"],
            ["Bad Status", "Desc", "unknown", "medium", ""],
        ],
    )
    response = client.post(
        "/api/import/projects/csv?organization_id=1",
        files={"file": ("projects.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 1
    assert len(body["errors"]) == 2
    assert "Name is required" in body["errors"][0]
    assert "Invalid status" in body["errors"][1]


def test_import_projects_csv_missing_org(client, auth_token):
    csv_data = _make_csv(["Name"], [["X"]])
    response = client.post(
        "/api/import/projects/csv?organization_id=999",
        files={"file": ("projects.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


# ── Task CSV import ─────────────────────────────────────────────────


def test_import_tasks_csv(client, auth_token):
    csv_data = _make_csv(
        ["Title", "Description", "Status", "Priority", "Assigned To", "Due Date", "Story Points"],
        [
            ["Task A", "Do A", "todo", "high", "", "", "3"],
            ["Task B", "Do B", "in_progress", "low", "", "", ""],
        ],
    )
    response = client.post(
        "/api/import/tasks/csv?project_id=1",
        files={"file": ("tasks.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 2
    assert body["errors"] == []


def test_import_tasks_csv_validation_errors(client, auth_token):
    csv_data = _make_csv(
        ["Title", "Description", "Status", "Priority", "Assigned To", "Due Date", "Story Points"],
        [
            ["", "No title", "todo", "medium", "", "", ""],
            ["Valid", "Ok", "todo", "medium", "", "", ""],
            ["Bad", "Desc", "invalid_status", "medium", "", "", ""],
        ],
    )
    response = client.post(
        "/api/import/tasks/csv?project_id=1",
        files={"file": ("tasks.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 1
    assert len(body["errors"]) == 2


def test_import_tasks_csv_missing_project(client, auth_token):
    csv_data = _make_csv(["Title"], [["X"]])
    response = client.post(
        "/api/import/tasks/csv?project_id=999",
        files={"file": ("tasks.csv", csv_data, "text/csv")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


# ── Project JSON import ─────────────────────────────────────────────


def test_import_projects_json(client, auth_token):
    data = [
        {"name": "Proj 1", "description": "Desc 1", "status": "active", "priority": "high", "budget": 5000},
        {"name": "Proj 2", "description": "Desc 2", "status": "completed", "priority": "low"},
    ]
    response = client.post(
        "/api/import/projects/json?organization_id=1",
        files={"file": ("projects.json", json.dumps(data).encode(), "application/json")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 2
    assert body["errors"] == []


def test_import_projects_json_validation_errors(client, auth_token):
    data = [
        {"name": "", "status": "active"},
        {"name": "Good", "status": "active"},
        {"name": "Bad", "status": "nope"},
    ]
    response = client.post(
        "/api/import/projects/json?organization_id=1",
        files={"file": ("projects.json", json.dumps(data).encode(), "application/json")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 1
    assert len(body["errors"]) == 2


def test_import_projects_json_invalid_format(client, auth_token):
    response = client.post(
        "/api/import/projects/json?organization_id=1",
        files={"file": ("projects.json", b"not json", "application/json")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400


def test_import_projects_json_not_array(client, auth_token):
    response = client.post(
        "/api/import/projects/json?organization_id=1",
        files={"file": ("projects.json", json.dumps({"name": "X"}).encode(), "application/json")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400


# ── Task JSON import ────────────────────────────────────────────────


def test_import_tasks_json(client, auth_token):
    data = [
        {"title": "Task 1", "description": "Do 1", "status": "todo", "priority": "high", "story_points": 5},
        {"title": "Task 2", "status": "in_progress"},
    ]
    response = client.post(
        "/api/import/tasks/json?project_id=1",
        files={"file": ("tasks.json", json.dumps(data).encode(), "application/json")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 2
    assert body["errors"] == []


def test_import_tasks_json_validation_errors(client, auth_token):
    data = [
        {"title": ""},
        {"title": "Good", "status": "todo"},
        {"title": "Bad", "status": "invalid"},
    ]
    response = client.post(
        "/api/import/tasks/json?project_id=1",
        files={"file": ("tasks.json", json.dumps(data).encode(), "application/json")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 1
    assert len(body["errors"]) == 2


def test_import_tasks_json_invalid_format(client, auth_token):
    response = client.post(
        "/api/import/tasks/json?project_id=1",
        files={"file": ("tasks.json", b"not json", "application/json")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400


# ── Authentication ──────────────────────────────────────────────────


def test_import_requires_auth(client):
    csv_data = _make_csv(["Name"], [["X"]])
    response = client.post(
        "/api/import/projects/csv?organization_id=1",
        files={"file": ("projects.csv", csv_data, "text/csv")},
    )
    assert response.status_code in (401, 403)
