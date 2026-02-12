import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.main import app
from backend.database import get_db
from backend.models import Base, User, Organization
from backend.security import get_password_hash

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
async def test_db():
    """Create test database with tables for every test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Seed a user + organization for auth
    async with factory() as session:
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("testpass123"),
            full_name="Test User",
        )
        session.add(user)
        await session.flush()

        org = Organization(
            name="Test Org",
            slug="test-org",
            description="Testing organization",
        )
        session.add(org)
        await session.commit()

    yield factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_header(client):
    """Register + login, return Authorization header."""
    # Use the seeded user
    resp = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpass123"},
    )
    # If the auth routes lack the /api/auth prefix, try without
    if resp.status_code == 404:
        resp = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass123"},
        )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Subscription tests ─────────────────────────────────────────

def test_create_subscription(client, auth_header):
    """Create a starter monthly subscription."""
    resp = client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter", "billing_cycle": "monthly"},
        headers=auth_header,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["plan"] == "starter"
    assert body["billing_cycle"] == "monthly"
    assert body["amount"] == 9900
    assert body["status"] == "active"
    assert body["currency"] == "USD"


def test_create_subscription_annual(client, auth_header):
    """Create a pro annual subscription."""
    resp = client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "pro", "billing_cycle": "annual"},
        headers=auth_header,
    )
    assert resp.status_code == 201
    assert resp.json()["amount"] == 322800


def test_create_duplicate_subscription_fails(client, auth_header):
    """Cannot create a second active subscription for same org."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    resp = client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "pro"},
        headers=auth_header,
    )
    assert resp.status_code == 409


def test_create_subscription_bad_org(client, auth_header):
    """Cannot subscribe to a non-existent organization."""
    resp = client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 9999, "plan": "starter"},
        headers=auth_header,
    )
    assert resp.status_code == 404


def test_create_subscription_invalid_plan(client, auth_header):
    """Invalid plan name is rejected by schema validation."""
    resp = client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "free"},
        headers=auth_header,
    )
    assert resp.status_code == 422


def test_list_subscriptions(client, auth_header):
    """List subscriptions for an org."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    resp = client.get(
        "/api/revenue/subscriptions?organization_id=1",
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_subscription(client, auth_header):
    """Get a single subscription by id."""
    create = client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "enterprise", "billing_cycle": "annual"},
        headers=auth_header,
    )
    sub_id = create.json()["id"]
    resp = client.get(f"/api/revenue/subscriptions/{sub_id}", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["plan"] == "enterprise"


def test_update_subscription(client, auth_header):
    """Upgrade a subscription plan."""
    create = client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    sub_id = create.json()["id"]
    resp = client.put(
        f"/api/revenue/subscriptions/{sub_id}",
        json={"plan": "pro"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert resp.json()["plan"] == "pro"
    assert resp.json()["amount"] == 29900


def test_cancel_subscription(client, auth_header):
    """Cancel an active subscription."""
    create = client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    sub_id = create.json()["id"]
    resp = client.delete(f"/api/revenue/subscriptions/{sub_id}", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Subscription canceled"


def test_cancel_already_canceled(client, auth_header):
    """Cannot cancel an already canceled subscription."""
    create = client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    sub_id = create.json()["id"]
    client.delete(f"/api/revenue/subscriptions/{sub_id}", headers=auth_header)
    resp = client.delete(f"/api/revenue/subscriptions/{sub_id}", headers=auth_header)
    assert resp.status_code == 400


# ── Invoice tests ──────────────────────────────────────────────

def test_invoice_created_with_subscription(client, auth_header):
    """Creating a subscription auto-generates an invoice."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    resp = client.get(
        "/api/revenue/invoices?organization_id=1",
        headers=auth_header,
    )
    assert resp.status_code == 200
    invoices = resp.json()
    assert len(invoices) == 1
    assert invoices[0]["amount"] == 9900
    assert invoices[0]["status"] == "pending"


def test_get_invoice(client, auth_header):
    """Get a specific invoice."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "pro"},
        headers=auth_header,
    )
    invoices = client.get(
        "/api/revenue/invoices?organization_id=1",
        headers=auth_header,
    ).json()
    inv_id = invoices[0]["id"]
    resp = client.get(f"/api/revenue/invoices/{inv_id}", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["amount"] == 29900


def test_filter_invoices_by_status(client, auth_header):
    """Filter invoices by status."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    resp = client.get(
        "/api/revenue/invoices?organization_id=1&status=paid",
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0  # none paid yet


# ── Payment tests ──────────────────────────────────────────────

def test_record_payment(client, auth_header):
    """Record a payment and mark invoice as paid."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    invoices = client.get(
        "/api/revenue/invoices?organization_id=1", headers=auth_header
    ).json()
    inv_id = invoices[0]["id"]

    resp = client.post(
        "/api/revenue/payments",
        json={
            "invoice_id": inv_id,
            "payment_method": "credit_card",
            "reference_id": "ch_test_123",
        },
        headers=auth_header,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount"] == 9900
    assert body["status"] == "completed"
    assert body["reference_id"] == "ch_test_123"

    # Invoice should now be paid
    inv = client.get(f"/api/revenue/invoices/{inv_id}", headers=auth_header).json()
    assert inv["status"] == "paid"
    assert inv["paid_at"] is not None


def test_double_payment_rejected(client, auth_header):
    """Cannot pay the same invoice twice."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    invoices = client.get(
        "/api/revenue/invoices?organization_id=1", headers=auth_header
    ).json()
    inv_id = invoices[0]["id"]

    client.post(
        "/api/revenue/payments",
        json={"invoice_id": inv_id, "payment_method": "credit_card"},
        headers=auth_header,
    )
    resp = client.post(
        "/api/revenue/payments",
        json={"invoice_id": inv_id, "payment_method": "credit_card"},
        headers=auth_header,
    )
    assert resp.status_code == 400


def test_list_payments(client, auth_header):
    """List payments for an org."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    invoices = client.get(
        "/api/revenue/invoices?organization_id=1", headers=auth_header
    ).json()
    client.post(
        "/api/revenue/payments",
        json={"invoice_id": invoices[0]["id"], "payment_method": "bank_transfer"},
        headers=auth_header,
    )
    resp = client.get(
        "/api/revenue/payments?organization_id=1", headers=auth_header
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Revenue metrics tests ─────────────────────────────────────

def test_revenue_metrics_empty(client, auth_header):
    """Metrics with no data returns zeroes."""
    resp = client.get("/api/revenue/metrics", headers=auth_header)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mrr"] == 0
    assert body["arr"] == 0
    assert body["active_subscriptions"] == 0
    assert body["total_collected"] == 0
    assert body["outstanding"] == 0


def test_revenue_metrics_with_subscription(client, auth_header):
    """Metrics reflect an active subscription."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    resp = client.get("/api/revenue/metrics", headers=auth_header)
    body = resp.json()
    assert body["mrr"] == 9900
    assert body["arr"] == 9900 * 12
    assert body["active_subscriptions"] == 1
    assert body["outstanding"] == 9900  # unpaid invoice


def test_revenue_metrics_after_payment(client, auth_header):
    """Metrics reflect collected revenue after payment."""
    client.post(
        "/api/revenue/subscriptions",
        json={"organization_id": 1, "plan": "starter"},
        headers=auth_header,
    )
    invoices = client.get(
        "/api/revenue/invoices?organization_id=1", headers=auth_header
    ).json()
    client.post(
        "/api/revenue/payments",
        json={"invoice_id": invoices[0]["id"], "payment_method": "credit_card"},
        headers=auth_header,
    )
    resp = client.get("/api/revenue/metrics", headers=auth_header)
    body = resp.json()
    assert body["total_collected"] == 9900
    assert body["outstanding"] == 0


def test_revenue_trend(client, auth_header):
    """Revenue trend returns daily aggregates."""
    resp = client.get("/api/revenue/metrics/trend", headers=auth_header)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_revenue_metrics_filtered_by_org(client, auth_header):
    """Metrics can be filtered to a specific organization."""
    resp = client.get("/api/revenue/metrics?organization_id=1", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["currency"] == "USD"
