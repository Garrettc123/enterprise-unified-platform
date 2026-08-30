"""Webhook client for pushing revenue events from Enterprise Hub to APEX Revenue System."""
import os
import hmac
import hashlib
import json
import httpx

APEX_URL = os.getenv("APEX_WEBHOOK_URL", "http://localhost:8000/webhook/enterprise_sync")
WEBHOOK_SECRET = os.getenv("ENTERPRISE_SYNC_SECRET", "super-secret-key")


async def send_revenue_sync(amount: float, transaction_id: str, customer_id: str = "", plan: str = ""):
    """Send an HMAC-secured revenue event to the APEX Revenue System."""
    payload = {
        "amount": amount,
        "transaction_id": transaction_id,
        "customer_id": customer_id,
        "plan": plan,
        "status": "cleared",
        "source": "enterprise-unified-platform",
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()

    headers = {
        "X-Enterprise-Signature": signature,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(APEX_URL, content=payload_bytes, headers=headers)
        resp.raise_for_status()
        return resp.json()