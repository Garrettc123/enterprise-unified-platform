import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import get_db
from backend.main import app
from backend.models import Base, User
from backend.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_db():
    """Create test database and override get_db dependency for every test."""
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

    yield session_factory

    app.dependency_overrides.clear()

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_teardown())


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app, raise_server_exceptions=False)


def _register_user(client, username="testuser", email="test@example.com",
                    password="testpass123", full_name="Test User"):
    """Helper to register a user."""
    return client.post(
        "/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": full_name,
        },
    )


def _login_user(client, username="testuser", password="testpass123"):
    """Helper to login a user and return the response."""
    return client.post(
        "/login",
        data={"username": username, "password": password},
    )


def _get_auth_header(client, username="testuser", password="testpass123"):
    """Helper to register, login, and return auth header."""
    resp = _login_user(client, username, password)
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Security utility tests
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_hash_password(self):
        hashed = get_password_hash("mypassword")
        assert hashed != "mypassword"
        assert isinstance(hashed, str)

    def test_verify_correct_password(self):
        hashed = get_password_hash("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        hash1 = get_password_hash("samepassword")
        hash2 = get_password_hash("samepassword")
        assert hash1 != hash2  # bcrypt salts differ


class TestTokenCreation:
    """Tests for JWT token creation and decoding."""

    def test_create_access_token(self):
        token = create_access_token(data={"sub": "testuser"})
        assert isinstance(token, str)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_custom_expiry(self):
        delta = timedelta(minutes=5)
        token = create_access_token(data={"sub": "u"}, expires_delta=delta)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "u"

    def test_create_refresh_token(self):
        token = create_refresh_token(data={"sub": "testuser"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

    def test_decode_valid_token(self):
        token = create_access_token(data={"sub": "alice"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "alice"

    def test_decode_invalid_token(self):
        assert decode_token("not.a.valid.token") is None

    def test_decode_expired_token(self):
        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(seconds=-1),
        )
        assert decode_token(token) is None

    def test_decode_token_wrong_secret(self):
        token = jwt.encode(
            {"sub": "testuser", "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong-secret",
            algorithm=ALGORITHM,
        )
        assert decode_token(token) is None


# ---------------------------------------------------------------------------
# Registration endpoint tests
# ---------------------------------------------------------------------------

class TestRegistration:
    """Tests for POST /register."""

    def test_register_success(self, client):
        response = _register_user(client)
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"
        assert data["is_active"] is True
        assert "id" in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client):
        _register_user(client, username="user1", email="dup@example.com")
        response = _register_user(client, username="user2", email="dup@example.com")
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_register_duplicate_username(self, client):
        _register_user(client, username="duped", email="a@example.com")
        response = _register_user(client, username="duped", email="b@example.com")
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_register_short_password(self, client):
        response = _register_user(client, password="short")
        assert response.status_code == 422  # Pydantic validation

    def test_register_short_username(self, client):
        response = _register_user(client, username="ab")
        assert response.status_code == 422

    def test_register_invalid_email(self, client):
        response = _register_user(client, email="not-an-email")
        assert response.status_code == 422

    def test_register_missing_required_fields(self, client):
        response = client.post("/register", json={})
        assert response.status_code == 422

    def test_register_without_full_name(self, client):
        response = client.post(
            "/register",
            json={
                "username": "nofullname",
                "email": "nofull@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 201
        assert response.json()["full_name"] is None


# ---------------------------------------------------------------------------
# Login endpoint tests
# ---------------------------------------------------------------------------

class TestLogin:
    """Tests for POST /login."""

    def test_login_success(self, client):
        _register_user(client)
        response = _login_user(client)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        _register_user(client)
        response = _login_user(client, password="wrongpassword")
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_nonexistent_user(self, client):
        response = _login_user(client, username="ghost", password="pass12345678")
        assert response.status_code == 401

    def test_login_inactive_user(self, client, setup_db):
        _register_user(client)

        # Deactivate the user directly in the database
        session_factory = setup_db

        async def deactivate():
            async with session_factory() as session:
                result = await session.execute(
                    select(User).where(User.username == "testuser")
                )
                user = result.scalar_one()
                user.is_active = False
                await session.commit()

        asyncio.run(deactivate())

        response = _login_user(client)
        assert response.status_code == 400
        assert "Inactive user" in response.json()["detail"]

    def test_login_returns_valid_jwt(self, client):
        _register_user(client)
        response = _login_user(client)
        token = response.json()["access_token"]
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"


# ---------------------------------------------------------------------------
# Get current user (/me) endpoint tests
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    """Tests for GET /me."""

    def test_get_me_success(self, client):
        _register_user(client)
        headers = _get_auth_header(client)
        response = client.get("/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    def test_get_me_no_token(self, client):
        response = client.get("/me")
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client):
        headers = {"Authorization": "Bearer invalidtoken"}
        response = client.get("/me", headers=headers)
        assert response.status_code == 401

    def test_get_me_expired_token(self, client):
        _register_user(client)
        expired_token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(seconds=-1),
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/me", headers=headers)
        assert response.status_code == 401

    def test_get_me_token_missing_sub(self, client):
        token = jwt.encode(
            {"exp": datetime.utcnow() + timedelta(hours=1)},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/me", headers=headers)
        assert response.status_code == 401

    def test_get_me_user_deleted(self, client, setup_db):
        """Token valid but user no longer exists in DB."""
        _register_user(client)
        headers = _get_auth_header(client)

        session_factory = setup_db

        async def delete_user():
            async with session_factory() as session:
                result = await session.execute(
                    select(User).where(User.username == "testuser")
                )
                user = result.scalar_one()
                await session.delete(user)
                await session.commit()

        asyncio.run(delete_user())

        response = client.get("/me", headers=headers)
        assert response.status_code == 401
        assert "User not found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# API key endpoint tests
# ---------------------------------------------------------------------------

class TestAPIKeys:
    """Tests for POST /api-keys and GET /api-keys."""

    def test_create_api_key(self, client):
        _register_user(client)
        headers = _get_auth_header(client)
        response = client.post(
            "/api-keys",
            json={"name": "my-key"},
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "my-key"
        assert data["key"].startswith("ep_")
        assert data["is_active"] is True

    def test_create_api_key_with_expiry(self, client):
        _register_user(client)
        headers = _get_auth_header(client)
        expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
        response = client.post(
            "/api-keys",
            json={"name": "expiring-key", "expires_at": expires},
            headers=headers,
        )
        assert response.status_code == 201
        assert response.json()["expires_at"] is not None

    def test_create_api_key_unauthenticated(self, client):
        response = client.post("/api-keys", json={"name": "my-key"})
        assert response.status_code == 401

    def test_create_api_key_missing_name(self, client):
        _register_user(client)
        headers = _get_auth_header(client)
        response = client.post("/api-keys", json={}, headers=headers)
        assert response.status_code == 422

    def test_list_api_keys_empty(self, client):
        _register_user(client)
        headers = _get_auth_header(client)
        response = client.get("/api-keys", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_api_keys_after_create(self, client):
        _register_user(client)
        headers = _get_auth_header(client)
        client.post("/api-keys", json={"name": "key1"}, headers=headers)
        client.post("/api-keys", json={"name": "key2"}, headers=headers)
        response = client.get("/api-keys", headers=headers)
        assert response.status_code == 200
        keys = response.json()
        assert len(keys) == 2
        names = {k["name"] for k in keys}
        assert names == {"key1", "key2"}

    def test_list_api_keys_unauthenticated(self, client):
        response = client.get("/api-keys")
        assert response.status_code == 401

    def test_api_keys_isolated_per_user(self, client):
        """Keys created by user A should not be visible to user B."""
        _register_user(client, username="alice", email="alice@example.com")
        _register_user(client, username="bob", email="bob@example.com")

        alice_headers = _get_auth_header(client, username="alice")
        bob_headers = _get_auth_header(client, username="bob")

        client.post("/api-keys", json={"name": "alice-key"}, headers=alice_headers)

        response = client.get("/api-keys", headers=bob_headers)
        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# Health check test (kept from original)
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """Tests for GET /health."""

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"