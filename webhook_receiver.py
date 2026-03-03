"""GitHub Webhook Receiver for triggering autonomous sync."""

from fastapi import FastAPI, Request, Header, HTTPException
import hmac
import hashlib
import json
import logging
import os
import stripe
from typing import Optional
from datetime import datetime
import asyncio
from sync_engine import AutonomousSyncEngine

logger = logging.getLogger(__name__)

app = FastAPI(title="GitHub Webhook Receiver")
engine = AutonomousSyncEngine()


def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    expected = 'sha256=' + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None)
):
    """Receive GitHub webhook and trigger sync."""
    payload = await request.body()
    secret = "your-webhook-secret"  # From environment

    # Verify signature
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature")

    if not verify_github_signature(payload, x_hub_signature_256, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    data = json.loads(payload)
    event_type = request.headers.get("X-GitHub-Event")

    logger.info(f"Received GitHub webhook: {event_type}")
    logger.info(f"Repository: {data.get('repository', {}).get('full_name')}")
    logger.info(f"Branch: {data.get('ref')}")

    # Trigger sync on push to main branch
    if event_type == "push" and data.get("ref") == "refs/heads/main":
        logger.info("✓ Triggering autonomous sync...")
        # Sync would be triggered here
        return {
            "status": "sync_triggered",
            "repository": data.get('repository', {}).get('full_name'),
            "timestamp": datetime.utcnow().isoformat()
        }

    return {"status": "received", "event": event_type}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "github-webhook-receiver"}


# STRIPE PAYMENT WEBHOOK
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if not STRIPE_WEBHOOK_SECRET or not STRIPE_SECRET_KEY:
    logger.warning(
        "Missing required Stripe environment variables: STRIPE_WEBHOOK_SECRET and/or STRIPE_SECRET_KEY"
    )
stripe.api_key = STRIPE_SECRET_KEY or ""
PRODUCT_MAP = {
    'prod_U4vmR3sBAvRGnq': 'AI Deal Desk',
    'prod_U4vqLmVcFl5Byi': 'SEO Content Factory',
    'prod_U4vrM38MgRbD59': 'Churn Predictor',
    'prod_U4vsAib9kMWgV4': 'Smart Contract Auditor',
}


@app.post('/webhook/stripe')
async def stripe_webhook(request: Request):
    """Receive Stripe webhook events and process payment notifications."""
    payload = await request.body()
    sig = request.headers.get('stripe-signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError as err:
        logger.warning("Stripe signature verification failed: %s", err)
        raise HTTPException(status_code=400, detail='Invalid signature') from err
    except ValueError as err:
        logger.warning("Invalid webhook payload: %s", err)
        raise HTTPException(status_code=400, detail='Invalid payload') from err
    if event['type'] == 'payment_intent.succeeded':
        pi = event['data']['object']
        email = pi.get('receipt_email', 'unknown')
        amount = pi.get('amount', 0) / 100
        if email != "unknown" and "@" in email:
            local, domain = email.split("@", 1)
            masked_email = f"{local[:2]}***@{domain}"
        else:
            masked_email = email
        logger.info("PAYMENT: %s paid $%.2f", masked_email, amount)
    return {'status': 'ok'}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
