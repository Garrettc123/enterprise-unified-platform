"""
Revenue Engine — FastAPI Router
================================
Handles all money-in flows:
  POST /revenue/checkout   — Stripe Checkout Session (one-time or subscription)
  POST /revenue/webhook    — Stripe webhook (payment_intent, invoice, subscription events)
  GET  /revenue/dashboard  — Live MRR/ARR/churn/LTV/pipeline metrics
  POST /revenue/invoice    — Manual invoice trigger for enterprise clients
  GET  /revenue/health     — Revenue system readiness probe

All Stripe API calls use the STRIPE_SECRET_KEY env var (GitHub Secret).
Webhook signature verified via STRIPE_WEBHOOK_SECRET.
No key is hardcoded anywhere in this file.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/revenue", tags=["revenue"])

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

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
    amount_cents: int = Field(..., gt=0, description="Amount in cents")
    currency: str = Field(default="usd")
    description: str
    due_days: int = Field(default=30)


# ---------------------------------------------------------------------------
# Stripe client wrapper (lazy import — only fails at call time if not installed)
# ---------------------------------------------------------------------------

def _stripe():
    try:
        import stripe as _s
        _s.api_key = os.environ["STRIPE_SECRET_KEY"]
        return _s
    except ImportError:
        raise HTTPException(status_code=503, detail="stripe package not installed")
    except KeyError:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY not set")


# ---------------------------------------------------------------------------
# In-memory revenue ledger (replace with DB in production)
# ---------------------------------------------------------------------------

_ledger: list[dict] = []


def _record_event(event_type: str, amount_cents: int, customer_id: str, meta: dict = None):
    _ledger.append({
        "ts": int(time.time()),
        "event": event_type,
        "amount_cents": amount_cents,
        "customer_id": customer_id,
        "meta": meta or {},
    })


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/health")
async def revenue_health():
    """Readiness probe — returns 200 if Stripe key is configured."""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key or not key.startswith("sk_"):
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": "STRIPE_SECRET_KEY missing or invalid"}
        )
    return {
        "status": "configured_unverified",
        "stripe_mode": "live" if key.startswith("sk_live_") else "test",
        "ledger_events": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/checkout")
async def create_checkout_session(req: CheckoutRequest):
    """Create a Stripe Checkout Session and return the redirect URL."""
    stripe = _stripe()
    try:
        session = stripe.checkout.Session.create(
            customer_email=req.customer_email,
            line_items=[{"price": req.price_id, "quantity": 1}],
            mode=req.mode,
            success_url=req.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=req.cancel_url,
            client_reference_id=req.client_reference_id,
            metadata=req.metadata,
        )
        return {
            "session_id": session.id,
            "checkout_url": session.url,
            "mode": req.mode,
            "customer_email": req.customer_email,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    """
    Stripe webhook endpoint. Verifies signature, dispatches event handlers.
    Register this URL in Stripe Dashboard → Webhooks.
    """
    payload = await request.body()
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Signed webhook processing is not configured")
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    stripe = _stripe()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, webhook_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")

    etype = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    # --- Payment succeeded
    if etype == "payment_intent.succeeded":
        amount = data.get("amount", 0)
        customer = data.get("customer") or "guest"
        _record_event("payment_succeeded", amount, customer, {"intent_id": data.get("id")})

    # --- Subscription created
    elif etype == "customer.subscription.created":
        plan = data.get("plan", {}).get("id", "")
        customer = data.get("customer", "")
        amount = data.get("plan", {}).get("amount", 0)
        _record_event("subscription_created", amount, customer, {"plan": plan})

    # --- Subscription deleted (churn)
    elif etype == "customer.subscription.deleted":
        customer = data.get("customer", "")
        amount = data.get("plan", {}).get("amount", 0)
        _record_event("subscription_churned", -amount, customer)

    # --- Invoice paid (recurring revenue)
    elif etype == "invoice.paid":
        customer = data.get("customer", "")
        amount = data.get("amount_paid", 0)
        _record_event("invoice_paid", amount, customer, {"invoice_id": data.get("id")})

    # --- Invoice payment failed
    elif etype == "invoice.payment_failed":
        customer = data.get("customer", "")
        _record_event("invoice_failed", 0, customer)

    return {"received": True, "event_type": etype}


@router.get("/dashboard")
async def revenue_dashboard():
    """Do not expose transient webhook counts as reconciled finance data."""
    return JSONResponse(
        status_code=503,
        content={
            "status": "unavailable",
            "reason": "Durable Stripe reconciliation has not been implemented",
            "verified_revenue": None,
            "verified_mrr": None,
            "verified_arr": None,
            "verified_customer_count": None,
        },
    )


@router.post("/invoice")
async def create_invoice(req: InvoiceRequest):
    """Manually create and finalize a Stripe invoice for enterprise billing."""
    stripe = _stripe()
    try:
        # Create invoice item
        stripe.InvoiceItem.create(
            customer=req.customer_id,
            amount=req.amount_cents,
            currency=req.currency,
            description=req.description,
        )
        # Create and finalize invoice
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
