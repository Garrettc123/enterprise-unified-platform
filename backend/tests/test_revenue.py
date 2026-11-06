"""
Revenue Engine Tests
=====================
pytest backend/tests/test_revenue.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")

from backend.routers.revenue import router, _record_event, _ledger
from backend.revenue_agent import (
    Lead, LeadScorer, RevenueSnapshot, RevenueForecaster,
    Account, ChurnPredictor, RevenueAutomationAgent,
)

app = FastAPI()
app.include_router(router)
client = TestClient(app)


# --- Revenue router tests ---

def test_health_check_no_key():
    del os.environ["STRIPE_SECRET_KEY"]
    r = client.get("/revenue/health")
    assert r.status_code == 503
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_placeholder"


def test_health_check_with_test_key():
    r = client.get("/revenue/health")
    assert r.status_code == 200
    assert r.json()["stripe_mode"] == "test"


def test_dashboard_returns_unavailable_without_durable_reconciliation():
    _ledger.clear()
    r = client.get("/revenue/dashboard")
    assert r.status_code == 503
    d = r.json()
    assert d["status"] == "unavailable"
    assert d["verified_mrr"] is None
    assert d["verified_arr"] is None


def test_volatile_events_cannot_be_reported_as_collected_revenue():
    _ledger.clear()
    _record_event("invoice_paid", 50000, "cus_test1")
    r = client.get("/revenue/dashboard")
    assert r.status_code == 503
    assert r.json()["verified_revenue"] is None


def test_webhook_refuses_unsigned_payload(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    r = client.post("/revenue/webhook", json={"type": "invoice.paid"})
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]


def test_checkout_requires_approved_product_catalog(monkeypatch):
    monkeypatch.delenv("GARCAR_ALLOWED_STRIPE_PRICE_IDS", raising=False)
    response = client.post("/revenue/checkout", json={
        "customer_email": "buyer@example.com",
        "price_id": "price_unapproved",
        "mode": "payment",
    })
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_checkout_rejects_unlisted_price_before_contacting_stripe(monkeypatch):
    monkeypatch.setenv("GARCAR_ALLOWED_STRIPE_PRICE_IDS", "price_verified")
    response = client.post("/revenue/checkout", json={
        "customer_email": "buyer@example.com",
        "price_id": "price_unapproved",
        "mode": "payment",
    })
    assert response.status_code == 400
    assert "approved catalog" in response.json()["detail"]


def test_checkout_rejects_non_verified_redirect_domain(monkeypatch):
    monkeypatch.setenv("GARCAR_ALLOWED_STRIPE_PRICE_IDS", "price_verified")
    monkeypatch.delenv("GARCAR_PUBLIC_BASE_URL", raising=False)
    response = client.post("/revenue/checkout", json={
        "customer_email": "buyer@example.com",
        "price_id": "price_verified",
        "mode": "payment",
        "success_url": "https://example.net/redirect",
    })
    assert response.status_code == 503
    assert "origin is not configured" in response.json()["detail"]


# --- LeadScorer tests ---

def test_lead_scorer_hot():
    scorer = LeadScorer()
    lead = Lead(id="1", email="cto@bigcorp.com", company_size=500,
                monthly_budget_usd=5000, intent_signals=4, source="referral")
    score = scorer.score(lead)
    assert score >= 75
    assert scorer.tier(score) == "HOT"


def test_lead_scorer_cold():
    scorer = LeadScorer()
    lead = Lead(id="2", email="anon@gmail.com", company_size=1,
                monthly_budget_usd=0, intent_signals=0, source="cold")
    score = scorer.score(lead)
    assert scorer.tier(score) in ("COLD", "DISQUALIFIED")


# --- RevenueForecaster tests ---

def test_forecaster_insufficient_data():
    f = RevenueForecaster()
    result = f.forecast([RevenueSnapshot(month=0, mrr=1000)])
    assert result["confidence"] == "low"


def test_forecaster_growth_trend():
    f = RevenueForecaster()
    history = [RevenueSnapshot(month=i * 2592000, mrr=1000 + i * 200) for i in range(6)]
    result = f.forecast(history)
    assert result["forecast_mrr"] > result["current_mrr"]
    assert result["growth_rate_pct"] > 0


# --- ChurnPredictor tests ---

def test_churn_at_risk():
    predictor = ChurnPredictor()
    account = Account(
        id="acc1", customer_email="at@risk.com", mrr=500,
        days_since_last_login=90, support_tickets_30d=3, payment_failures_30d=2,
        feature_usage_score=10, contract_days_remaining=15,
    )
    assert predictor.at_risk(account)
    assert predictor.risk_score(account) >= 60


def test_churn_healthy():
    predictor = ChurnPredictor()
    account = Account(
        id="acc2", customer_email="happy@customer.com", mrr=1000,
        days_since_last_login=1, support_tickets_30d=0, payment_failures_30d=0,
        feature_usage_score=95, contract_days_remaining=300,
    )
    assert not predictor.at_risk(account)


# --- RevenueAutomationAgent tests ---

@pytest.mark.asyncio
async def test_agent_run_cycle():
    agent = RevenueAutomationAgent()
    leads = [
        Lead(id="L1", email="hot@lead.com", company_size=200,
             monthly_budget_usd=3000, intent_signals=3, source="referral"),
    ]
    accounts = []
    history = [RevenueSnapshot(month=i * 2592000, mrr=1000 + i * 100) for i in range(4)]
    result = await agent.run_cycle(leads=leads, accounts=accounts, history=history)
    assert result["leads_scored"] == 1
    assert result["cycle"] == 1
    assert "forecast" in result
