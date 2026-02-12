"""Tests for Elasticsearch search functionality.

Tests the search endpoints with database fallback (no ES available)
and mocked Elasticsearch service for ES-powered search.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.main import app
from backend.database import get_db
from backend.models import Base, User, Organization, Project, Task
from backend.security import get_password_hash
from backend.elasticsearch_service import ElasticsearchService

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def setup_db():
    """Create test database synchronously using asyncio.run()"""
    import asyncio

    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return engine

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
def client(setup_db):
    """Create test client with rate limiter cleared."""
    # Clear rate limiter state
    middleware = app.middleware_stack
    while middleware:
        if hasattr(middleware, "app"):
            inner = middleware.app
            if hasattr(inner, "requests"):
                inner.requests.clear()
            middleware = inner
        else:
            break

    return TestClient(app)


@pytest.fixture
def auth_token(client, setup_db):
    """Register a user and return the auth token."""
    import asyncio

    session_factory = setup_db

    async def _create_user():
        async with session_factory() as session:
            user = User(
                username="searchuser",
                email="search@example.com",
                full_name="Search User",
                hashed_password=get_password_hash("testpass123"),
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user.id

    user_id = asyncio.run(_create_user())

    # Login to get token
    response = client.post(
        "/login",
        data={"username": "searchuser", "password": "testpass123"},
    )
    if response.status_code == 200:
        return response.json()["access_token"]

    # If login doesn't work at /login, try /api/auth/login
    response = client.post(
        "/api/auth/login",
        data={"username": "searchuser", "password": "testpass123"},
    )
    if response.status_code == 200:
        return response.json()["access_token"]

    # Create a token directly
    from backend.security import create_access_token
    return create_access_token(data={"sub": "searchuser"})


@pytest.fixture
def seed_data(setup_db):
    """Seed test data for search."""
    import asyncio

    session_factory = setup_db

    async def _seed():
        async with session_factory() as session:
            user = User(
                username="testuser",
                email="test@example.com",
                full_name="Test User",
                hashed_password=get_password_hash("testpass123"),
                is_active=True,
            )
            session.add(user)
            await session.flush()

            org = Organization(
                name="Test Org",
                slug="test-org",
                description="A test organization",
            )
            session.add(org)
            await session.flush()

            project = Project(
                name="Alpha Project",
                description="The first alpha project for testing",
                organization_id=org.id,
                created_by=user.id,
                status="active",
                priority="high",
            )
            session.add(project)
            await session.flush()

            task = Task(
                title="Alpha Task",
                description="An alpha task for the project",
                project_id=project.id,
                created_by=user.id,
                status="todo",
                priority="medium",
            )
            session.add(task)
            await session.commit()

            return {
                "user_id": user.id,
                "org_id": org.id,
                "project_id": project.id,
                "task_id": task.id,
            }

    return asyncio.run(_seed())


# --- Test Database Fallback Search ---

def test_global_search_db_fallback(client, auth_token, seed_data):
    """Test global search falls back to database when ES is unavailable."""
    org_id = seed_data["org_id"]
    response = client.get(
        "/api/search/",
        params={"q": "Alpha", "organization_id": org_id},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "database"
    assert data["query"] == "Alpha"
    assert data["total"] > 0
    # Should find at least the project or task with "Alpha" in the name
    types_found = {r["type"] for r in data["results"]}
    assert "project" in types_found or "task" in types_found


def test_global_search_with_type_filter(client, auth_token, seed_data):
    """Test global search with type_filter parameter."""
    org_id = seed_data["org_id"]
    response = client.get(
        "/api/search/",
        params={"q": "Alpha", "organization_id": org_id, "type_filter": "project"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "database"
    for result in data["results"]:
        assert result["type"] == "project"


def test_global_search_no_results(client, auth_token, seed_data):
    """Test global search returns empty results for non-matching query."""
    org_id = seed_data["org_id"]
    response = client.get(
        "/api/search/",
        params={"q": "nonexistentxyz", "organization_id": org_id},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["results"] == []


def test_search_requires_auth(client, seed_data):
    """Test that search endpoints require authentication."""
    org_id = seed_data["org_id"]
    response = client.get(
        "/api/search/",
        params={"q": "test", "organization_id": org_id},
    )
    # Should require auth
    assert response.status_code in (401, 403, 422)


def test_search_query_min_length(client, auth_token, seed_data):
    """Test that query requires minimum 2 characters."""
    org_id = seed_data["org_id"]
    response = client.get(
        "/api/search/",
        params={"q": "a", "organization_id": org_id},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422


def test_search_projects_endpoint(client, auth_token, seed_data):
    """Test the /api/search/projects endpoint."""
    org_id = seed_data["org_id"]
    response = client.get(
        "/api/search/projects",
        params={"q": "Alpha", "organization_id": org_id},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["name"] == "Alpha Project"


def test_search_tasks_endpoint(client, auth_token, seed_data):
    """Test the /api/search/tasks endpoint."""
    org_id = seed_data["org_id"]
    response = client.get(
        "/api/search/tasks",
        params={"q": "Alpha", "organization_id": org_id},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["title"] == "Alpha Task"


# --- Test Suggestions Endpoint ---

def test_suggestions_db_fallback(client, auth_token, seed_data):
    """Test suggestions endpoint with database fallback."""
    response = client.get(
        "/api/search/suggestions",
        params={"q": "Al"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should find Alpha Project and Alpha Task
    titles = [s["title"] for s in data]
    assert any("Alpha" in t for t in titles)


# --- Test Reindex Endpoint ---

def test_reindex_without_es(client, auth_token, seed_data):
    """Test reindex fails gracefully when ES is unavailable."""
    response = client.post(
        "/api/search/reindex/projects",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 503


def test_reindex_invalid_entity_type(client, auth_token, seed_data):
    """Test reindex with invalid entity type."""
    # Mock ES as available
    mock_es = MagicMock(spec=ElasticsearchService)
    mock_es.is_available = True
    mock_es.bulk_index = AsyncMock(return_value={"indexed": 0, "errors": 0})

    with patch("backend.routers.search.get_elasticsearch_service", return_value=mock_es):
        response = client.post(
            "/api/search/reindex/invalid_type",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 400


# --- Test Elasticsearch Integration (Mocked) ---

def test_global_search_with_es(client, auth_token, seed_data):
    """Test global search uses Elasticsearch when available."""
    mock_es = MagicMock(spec=ElasticsearchService)
    mock_es.is_available = True
    mock_es.search = AsyncMock(return_value={
        "results": [
            {
                "type": "project",
                "id": 1,
                "title": "Alpha Project",
                "description": "The first alpha project",
                "score": 5.2,
                "url": "/projects/1",
                "highlights": {"name": ["<em>Alpha</em> Project"]},
            }
        ],
        "total": 1,
    })

    with patch("backend.routers.search.get_elasticsearch_service", return_value=mock_es):
        response = client.get(
            "/api/search/",
            params={"q": "Alpha", "organization_id": seed_data["org_id"]},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "elasticsearch"
    assert data["total"] == 1
    assert data["results"][0]["title"] == "Alpha Project"
    assert data["results"][0]["score"] == 5.2


def test_suggestions_with_es(client, auth_token, seed_data):
    """Test suggestions uses Elasticsearch when available."""
    mock_es = MagicMock(spec=ElasticsearchService)
    mock_es.is_available = True
    mock_es.suggest = AsyncMock(return_value=[
        {"type": "project", "id": 1, "title": "Alpha Project"},
        {"type": "task", "id": 1, "title": "Alpha Task"},
    ])

    with patch("backend.routers.search.get_elasticsearch_service", return_value=mock_es):
        response = client.get(
            "/api/search/suggestions",
            params={"q": "Al"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Alpha Project"


# --- Test SearchResponse Schema ---

def test_search_response_schema(client, auth_token, seed_data):
    """Test that search response matches the SearchResponse schema."""
    org_id = seed_data["org_id"]
    response = client.get(
        "/api/search/",
        params={"q": "Alpha", "organization_id": org_id},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify schema fields
    assert "results" in data
    assert "total" in data
    assert "query" in data
    assert "source" in data
    assert isinstance(data["results"], list)
    assert isinstance(data["total"], int)

    if data["results"]:
        result = data["results"][0]
        assert "type" in result
        assert "id" in result
        assert "title" in result
        assert "url" in result


# --- Test ElasticsearchService Unit Tests ---

def test_elasticsearch_service_init():
    """Test ElasticsearchService initialization."""
    es = ElasticsearchService(
        elasticsearch_url="http://localhost:9200",
        index_prefix="test",
    )
    assert es.elasticsearch_url == "http://localhost:9200"
    assert es.index_prefix == "test"
    assert not es.is_available
    assert es.client is None


def test_elasticsearch_index_name():
    """Test index name generation."""
    es = ElasticsearchService(
        elasticsearch_url="http://localhost:9200",
        index_prefix="myapp",
    )
    assert es._index_name("projects") == "myapp_projects"
    assert es._index_name("tasks") == "myapp_tasks"
    assert es._index_name("users") == "myapp_users"


def test_elasticsearch_not_available_operations():
    """Test that operations return gracefully when ES is not available."""
    import asyncio

    es = ElasticsearchService(
        elasticsearch_url="http://localhost:9200",
        index_prefix="test",
    )

    async def _test():
        result = await es.search("test query")
        assert result == {"results": [], "total": 0}

        result = await es.suggest("test")
        assert result == []

        result = await es.index_document("projects", 1, {"name": "test"})
        assert result is False

        result = await es.bulk_index("projects", [])
        assert result == {"indexed": 0, "errors": 0}

        result = await es.delete_document("projects", 1)
        assert result is False

    asyncio.run(_test())
