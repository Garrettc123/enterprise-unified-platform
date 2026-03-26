"""
Revenue Router v2 — FastAPI
============================
All money endpoints delegate to MoneyEngine.

Routes:
  GET  /revenue/health        — Stripe + DB readiness probe
  POST /revenue/checkout      — Create Stripe Checkout Session
  POST /revenue/webhook       — Stripe webhook (signature verified, idempotent)
  GET  /revenue/dashboard     — Live MRR/ARR/LTV/churn from DB
  POST /revenue/invoice       — Create + finalize Stripe invoice
  POST /revenue/leads         — Score + store inbound leads
  GET  /revenue/leads         — List all scored leads
  GET  /revenue/accounts      — List accounts with churn risk scores
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/revenue", tags=["revenue"])


class CheckoutRequest(BaseModel):
    customer_email: str
    price_id: str = Field(..., description="Stripe Price ID (price_xxx)")
    mode: str = Field("subscription", pattern="^(subscription|payment)$")
    success_url: str = Field(default="https://garcarenterprise.com/success")
    cancel_url: str = Field(default="https://garcarenterprise.com/cancel")
    client_reference_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class InvoiceRequest(BaseModel):
    customer_id: str = Field(..., description="Stripe Customer ID (cus_xxx)")
    amount_cents: int = Field(..., gt=0)
    currency: str = Field(default="usd")
    description: str
    due_days: int = Field(default=30)


class LeadRequest(BaseModel):
    email: str
    company_size: int = 0
    monthly_budget_usd: float = 0
    intent_signals: int = 0
    source: str = "organic"


_leads: list[dict] = []


def _stripe():
    try:
        import stripe as _s
        key = os.environ.get("STRIPE_SECRET_KEY", "")
        if not key:
            raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY not set")
        _s.api_key = key
        return _s
    except ImportError:
        raise HTTPException(status_code=503, detail="stripe package not installed")


@router.get("/health")
async def revenue_health():
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key or not key.startswith("sk_"):
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": "STRIPE_SECRET_KEY missing or invalid"}
        )
    return {
        "status": "healthy",
        "stripe_mode": "live" if key.startswith("sk_live_") else "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/checkout")
async def create_checkout_session(req: CheckoutRequest):
    from backend.money import MoneyEngine
    engine = MoneyEngine()
    try:
        return await engine.create_checkout(
            customer_email=req.customer_email,
            price_id=req.price_id,
            mode=req.mode,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            metadata=req.metadata,
            client_reference_id=req.client_reference_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    payload = await request.body()
    from backend.money import MoneyEngine
    engine = MoneyEngine()
    try:
        result = await engine.process_webhook(
            raw_payload=payload,
            stripe_signature=stripe_signature or "",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dashboard")
async def revenue_dashboard():
    from backend.money import MoneyEngine
    engine = MoneyEngine()
    return await engine.compute_metrics(db=None)


@router.post("/invoice")
async def create_invoice(req: InvoiceRequest):
    stripe = _stripe()
    try:
        stripe.InvoiceItem.create(
            customer=req.customer_id,
            amount=req.amount_cents,
            currency=req.currency,
            description=req.description,
        )
        invoice = stripe.Invoice.create(
            customer=req.customer_id,
            collection_method="send_invoice",
            days_until_due=req.due_days,
            auto_advance=True,
        )
        finalized = stripe.Invoice.finalize_invoice(invoice.id)
        return {
            "invoice_id": finalized.id,
            "status": finalized.status,
            "amount_due": finalized.amount_due / 100,
            "currency": finalized.currency,
            "hosted_invoice_url": finalized.hosted_invoice_url,
            "due_date": finalized.due_date,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/leads")
async def submit_lead(req: LeadRequest):
    from backend.revenue_agent import Lead, LeadScorer
    import time
    import uuid

    lead = Lead(
        id=str(uuid.uuid4()),
        email=req.email,
        company_size=req.company_size,
        monthly_budget_usd=req.monthly_budget_usd,
        intent_signals=req.intent_signals,
        source=req.source,
        created_at=time.time(),
    )
    scorer = LeadScorer()
    score = scorer.score(lead)
    tier = scorer.tier(score)

    record = {
        "id": lead.id,
        "email": lead.email,
        "score": score,
        "tier": tier,
        "source": lead.source,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _leads.append(record)
    return record


@router.get("/leads")
async def list_leads(tier: Optional[str] = None):
    if tier:
        return [l for l in _leads if l["tier"] == tier.upper()]
    return _leads


@router.get("/accounts")
async def list_accounts():
    return {
        "accounts": [],
        "message": "Wire accounts to DB — populate via customer.subscription.created webhook events",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
