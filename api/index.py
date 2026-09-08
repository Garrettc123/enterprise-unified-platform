"""Garcar Enterprise Platform - Vercel Serverless Entry Point"""
import os

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

app = FastAPI(
    title="Garcar Enterprise Platform",
    description="Autonomous revenue infrastructure - Stripe billing, lead scoring, churn prediction.",
    version="2.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "status": "live",
        "platform": "Garcar Enterprise",
        "version": "2.0.1",
        "revenue_endpoints": [
            "/revenue/checkout",
            "/revenue/webhook",
            "/revenue/invoice",
            "/revenue/health"
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "platform": "Garcar Enterprise Platform", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/revenue/health")
async def revenue_health():
    return {"status": "healthy", "module": "revenue", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/revenue/checkout")
async def checkout_info():
    return {"endpoint": "checkout", "status": "operational", "provider": "stripe"}


@app.post("/revenue/webhook")
async def webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="stripe-signature")):
    """Launch-safe: refuse unsigned or unverified events. Do not mark processed."""
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature")
    if not os.environ.get("STRIPE_WEBHOOK_SECRET"):
        raise HTTPException(status_code=503, detail="Webhook signing secret is not configured")
    raise HTTPException(
        status_code=501,
        detail="Unsigned processing disabled. Use the signature-verified canonical webhook.",
    )


@app.get("/api/v1/status")
async def api_status():
    return {
        "platform": "Garcar Enterprise",
        "version": "2.0.1",
        "modules": ["revenue", "billing", "leads", "churn"],
        "status": "operational"
    }
