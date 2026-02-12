import asyncio
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.main import app
from backend.database import get_db
from backend.models import Base, User, EmailNotificationPreference
from backend.security import get_password_hash
from backend.email_service import EmailService, EMAIL_TEMPLATES

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_db():
    """Create test database and override dependency."""
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
    """Create test client."""
    return TestClient(app)


def _register_and_login(client):
    """Helper to register a user and return auth headers."""
    client.post(
        "/register",
        json={
            "username": "emailuser",
            "email": "emailuser@example.com",
            "password": "testpass123",
            "full_name": "Email User",
        },
    )
    response = client.post(
        "/login",
        data={"username": "emailuser", "password": "testpass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ------- EmailService unit tests -------

class TestEmailService:
    """Unit tests for EmailService."""

    def test_build_message(self):
        """Test building a MIME message."""
        service = EmailService(enabled=False)
        msg = service._build_message(
            to_email="test@example.com",
            subject="Test Subject",
            html_body="<p>Hello</p>",
            text_body="Hello",
        )
        assert msg["To"] == "test@example.com"
        assert msg["Subject"] == "Test Subject"
        assert "Enterprise Unified Platform" in msg["From"]

    def test_send_email_disabled(self):
        """Test that send_email returns False when disabled."""
        service = EmailService(enabled=False)
        result = service.send_email(
            to_email="test@example.com",
            subject="Test",
            html_body="<p>Test</p>",
        )
        assert result is False

    @patch("backend.email_service.smtplib.SMTP")
    def test_send_email_enabled_with_tls(self, mock_smtp_class):
        """Test sending email with TLS enabled."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        service = EmailService(
            enabled=True,
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            use_tls=True,
        )
        result = service.send_email(
            to_email="recipient@example.com",
            subject="Test",
            html_body="<p>Test</p>",
        )
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.sendmail.assert_called_once()

    @patch("backend.email_service.smtplib.SMTP")
    def test_send_email_enabled_without_tls(self, mock_smtp_class):
        """Test sending email without TLS."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        service = EmailService(
            enabled=True,
            smtp_host="smtp.test.com",
            smtp_port=25,
            smtp_username="",
            smtp_password="",
            use_tls=False,
        )
        result = service.send_email(
            to_email="recipient@example.com",
            subject="Test",
            html_body="<p>Test</p>",
        )
        assert result is True
        mock_server.starttls.assert_not_called()
        mock_server.login.assert_not_called()
        mock_server.sendmail.assert_called_once()

    @patch("backend.email_service.smtplib.SMTP")
    def test_send_email_failure(self, mock_smtp_class):
        """Test handling of SMTP failure."""
        mock_smtp_class.side_effect = OSError("Connection refused")

        service = EmailService(enabled=True, smtp_host="bad.host", smtp_port=587)
        result = service.send_email(
            to_email="recipient@example.com",
            subject="Test",
            html_body="<p>Test</p>",
        )
        assert result is False

    def test_send_notification_known_type(self):
        """Test sending notification with known type."""
        service = EmailService(enabled=False)
        result = service.send_notification(
            to_email="test@example.com",
            notification_type="task_assigned",
            context={
                "task_title": "Fix bug",
                "project_name": "Project A",
                "priority": "high",
                "assigned_by": "admin",
                "description": "Fix the login bug",
            },
        )
        assert result is False  # disabled, but no error

    def test_send_notification_unknown_type_falls_back(self):
        """Test that unknown notification type falls back to general."""
        service = EmailService(enabled=False)
        result = service.send_notification(
            to_email="test@example.com",
            notification_type="unknown_type",
            context={"subject": "Test", "body": "Test body"},
        )
        assert result is False  # disabled, but no error

    def test_get_supported_notification_types(self):
        """Test listing supported notification types."""
        service = EmailService()
        types = service.get_supported_notification_types()
        assert "task_assigned" in types
        assert "task_updated" in types
        assert "comment_added" in types
        assert "project_invitation" in types
        assert "general" in types

    def test_email_templates_have_required_keys(self):
        """Test that all templates have subject, html, and text."""
        for name, template in EMAIL_TEMPLATES.items():
            assert "subject" in template, f"Template {name} missing 'subject'"
            assert "html" in template, f"Template {name} missing 'html'"
            assert "text" in template, f"Template {name} missing 'text'"


# ------- API endpoint tests -------

class TestEmailNotificationEndpoints:
    """Tests for email notification API endpoints."""

    def test_get_preferences_creates_defaults(self, client, setup_db):
        """Test that GET preferences creates defaults for new user."""
        headers = _register_and_login(client)
        response = client.get("/api/email-notifications/preferences", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email_enabled"] is True
        assert data["task_assigned"] is True
        assert data["task_updated"] is True
        assert data["comment_added"] is True
        assert data["project_invitation"] is True

    def test_update_preferences(self, client, setup_db):
        """Test updating email notification preferences."""
        headers = _register_and_login(client)
        # First get defaults
        client.get("/api/email-notifications/preferences", headers=headers)

        # Update preferences
        response = client.put(
            "/api/email-notifications/preferences",
            headers=headers,
            json={
                "email_enabled": True,
                "task_assigned": False,
                "task_updated": True,
                "comment_added": False,
                "project_invitation": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_assigned"] is False
        assert data["comment_added"] is False

    def test_update_preferences_creates_if_not_exists(self, client, setup_db):
        """Test PUT creates preferences if they don't exist yet."""
        headers = _register_and_login(client)
        response = client.put(
            "/api/email-notifications/preferences",
            headers=headers,
            json={
                "email_enabled": False,
                "task_assigned": False,
                "task_updated": False,
                "comment_added": False,
                "project_invitation": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email_enabled"] is False

    def test_send_email_notification(self, client, setup_db):
        """Test sending email notification endpoint."""
        headers = _register_and_login(client)
        response = client.post(
            "/api/email-notifications/send",
            headers=headers,
            json={
                "to_email": "recipient@example.com",
                "notification_type": "general",
                "context": {"subject": "Test", "body": "Hello"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Email is disabled by default in tests
        assert data["success"] is False
        assert "disabled" in data["message"].lower() or "failed" in data["message"].lower()

    def test_get_notification_types(self, client, setup_db):
        """Test getting supported notification types."""
        headers = _register_and_login(client)
        response = client.get("/api/email-notifications/types", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "notification_types" in data
        assert "task_assigned" in data["notification_types"]

    def test_endpoints_require_authentication(self, client):
        """Test that endpoints require authentication."""
        response = client.get("/api/email-notifications/preferences")
        assert response.status_code in (401, 403)

        response = client.put(
            "/api/email-notifications/preferences",
            json={"email_enabled": True},
        )
        assert response.status_code in (401, 403)

        response = client.post(
            "/api/email-notifications/send",
            json={"to_email": "test@example.com", "notification_type": "general", "context": {}},
        )
        assert response.status_code in (401, 403)

        response = client.get("/api/email-notifications/types")
        assert response.status_code in (401, 403)
