import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.main import app
from backend.database import get_db
from backend.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_db():
    """Create test database and override dependency."""
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

    # Clear rate limiter state
    middleware = app.middleware_stack
    while middleware is not None:
        if hasattr(middleware, "app"):
            inner = middleware.app
            if hasattr(inner, "requests"):
                inner.requests.clear()
            middleware = inner
        else:
            break

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


def _register_and_login(client):
    """Helper: register a user and return an auth token."""
    client.post(
        "/register",
        json={
            "username": "payuser",
            "email": "pay@example.com",
            "password": "testpass123",
            "full_name": "Pay User",
        },
    )
    resp = client.post(
        "/login",
        data={"username": "payuser", "password": "testpass123"},
    )
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_payment_intent_no_stripe_key(client):
    """Should return 503 when Stripe is not configured."""
    token = _register_and_login(client)
    with patch("backend.routers.payments.settings") as mock_settings:
        mock_settings.STRIPE_SECRET_KEY = ""
        resp = client.post(
            "/api/payments/create-payment-intent",
            json={"amount": 5000, "currency": "usd"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 503


def test_create_payment_intent_success(client):
    """Should create a payment intent and store a record."""
    token = _register_and_login(client)

    mock_intent = MagicMock()
    mock_intent.id = "pi_test_123"
    mock_intent.status = "requires_payment_method"

    with patch("backend.routers.payments._get_stripe_client") as mock_client_fn:
        mock_stripe = MagicMock()
        mock_stripe.payment_intents.create.return_value = mock_intent
        mock_client_fn.return_value = mock_stripe

        resp = client.post(
            "/api/payments/create-payment-intent",
            json={"amount": 5000, "currency": "usd", "description": "Test payment"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["stripe_payment_intent_id"] == "pi_test_123"
    assert data["amount"] == 5000
    assert data["currency"] == "usd"
    assert data["status"] == "requires_payment_method"


def test_get_payment(client):
    """Should retrieve a payment by ID."""
    token = _register_and_login(client)

    mock_intent = MagicMock()
    mock_intent.id = "pi_test_456"
    mock_intent.status = "requires_payment_method"

    with patch("backend.routers.payments._get_stripe_client") as mock_client_fn:
        mock_stripe = MagicMock()
        mock_stripe.payment_intents.create.return_value = mock_intent
        mock_client_fn.return_value = mock_stripe

        create_resp = client.post(
            "/api/payments/create-payment-intent",
            json={"amount": 3000, "currency": "usd"},
            headers={"Authorization": f"Bearer {token}"},
        )

    payment_id = create_resp.json()["id"]

    resp = client.get(
        f"/api/payments/{payment_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == payment_id


def test_get_payment_not_found(client):
    """Should return 404 for non-existent payment."""
    token = _register_and_login(client)
    resp = client.get(
        "/api/payments/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_list_payments(client):
    """Should list all payments for the current user."""
    token = _register_and_login(client)

    mock_intent = MagicMock()
    mock_intent.id = "pi_list_1"
    mock_intent.status = "requires_payment_method"

    with patch("backend.routers.payments._get_stripe_client") as mock_client_fn:
        mock_stripe = MagicMock()
        mock_stripe.payment_intents.create.return_value = mock_intent
        mock_client_fn.return_value = mock_stripe

        client.post(
            "/api/payments/create-payment-intent",
            json={"amount": 1000, "currency": "usd"},
            headers={"Authorization": f"Bearer {token}"},
        )

        mock_intent.id = "pi_list_2"
        client.post(
            "/api/payments/create-payment-intent",
            json={"amount": 2000, "currency": "usd"},
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = client.get(
        "/api/payments/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_webhook_missing_secret(client):
    """Should return 503 when webhook secret is not configured."""
    with patch("backend.routers.payments.settings") as mock_settings:
        mock_settings.STRIPE_WEBHOOK_SECRET = ""
        resp = client.post(
            "/api/payments/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert resp.status_code == 503


def test_webhook_invalid_signature(client):
    """Should return 400 for invalid webhook signature."""
    with patch("backend.routers.payments.settings") as mock_settings:
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        resp = client.post(
            "/api/payments/webhook",
            content=b'{"type":"payment_intent.succeeded"}',
            headers={"stripe-signature": "t=1,v1=bad"},
        )
    assert resp.status_code == 400


def test_webhook_updates_payment(client):
    """Should update payment status on valid webhook event."""
    token = _register_and_login(client)

    # Create a payment first
    mock_intent = MagicMock()
    mock_intent.id = "pi_webhook_1"
    mock_intent.status = "requires_payment_method"

    with patch("backend.routers.payments._get_stripe_client") as mock_client_fn:
        mock_stripe = MagicMock()
        mock_stripe.payment_intents.create.return_value = mock_intent
        mock_client_fn.return_value = mock_stripe

        client.post(
            "/api/payments/create-payment-intent",
            json={"amount": 7500, "currency": "usd"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # Simulate webhook
    mock_event = MagicMock()
    mock_event.type = "payment_intent.succeeded"
    mock_event.data.object = {
        "id": "pi_webhook_1",
        "status": "succeeded",
        "payment_method_types": ["card"],
        "customer": "cus_123",
    }

    with patch("backend.routers.payments.settings") as mock_settings, \
         patch("backend.routers.payments.stripe.Webhook.construct_event", return_value=mock_event):
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        resp = client.post(
            "/api/payments/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=abc"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # Verify payment was updated
    get_resp = client.get(
        "/api/payments/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.json()["status"] == "succeeded"
    assert get_resp.json()["payment_method_type"] == "card"
    assert get_resp.json()["stripe_customer_id"] == "cus_123"
