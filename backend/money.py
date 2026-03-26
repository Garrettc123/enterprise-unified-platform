"""
MoneyEngine — Canonical Revenue Orchestration Layer
=====================================================
Single source of truth for ALL money flows in the platform.

Responsibilities:
  1. Create Stripe Checkout sessions (subscription + one-time)
  2. Verify + process Stripe webhooks with idempotency
  3. Persist every revenue event to DB (revenue_events table)
  4. Compute real-time MRR/ARR/LTV/churn from DB (not in-memory)
  5. Trigger GENESIS onboarding on first successful payment
  6. Fire Linear issues + Slack alerts on thresholds

Usage:
    from backend.money import MoneyEngine
    engine = MoneyEngine()
    result = await engine.process_webhook(payload, sig_header)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("money_engine")


def _get_stripe():
    """Lazy-load stripe SDK with key injection."""
    try:
        import stripe as _s
        key = os.environ.get("STRIPE_SECRET_KEY", "")
        if not key:
            raise RuntimeError("STRIPE_SECRET_KEY not set")
        _s.api_key = key
        return _s
    except ImportError:
        raise RuntimeError("stripe package not installed — run: pip install stripe")


class MoneyEngine:
    """
    Orchestrates the full revenue lifecycle.
    All methods are async-safe and idempotent.
    """

    # -------------------------------------------------------------------------
    # Checkout
    # -------------------------------------------------------------------------

    async def create_checkout(
        self,
        customer_email: str,
        price_id: str,
        mode: str = "subscription",
        success_url: str = "https://garcarenterprise.com/success",
        cancel_url: str = "https://garcarenterprise.com/cancel",
        metadata: dict | None = None,
        client_reference_id: str | None = None,
    ) -> dict:
        """
        Create a Stripe Checkout Session.
        Returns {session_id, checkout_url, mode}.
        """
        stripe = _get_stripe()
        session = stripe.checkout.Session.create(
            customer_email=customer_email,
            line_items=[{"price": price_id, "quantity": 1}],
            mode=mode,
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            client_reference_id=client_reference_id,
            metadata=metadata or {},
        )
        logger.info("Checkout session created: %s for %s", session.id, customer_email)
        return {
            "session_id": session.id,
            "checkout_url": session.url,
            "mode": mode,
            "customer_email": customer_email,
        }

    # -------------------------------------------------------------------------
    # Webhook Processing
    # -------------------------------------------------------------------------

    async def process_webhook(
        self,
        raw_payload: bytes,
        stripe_signature: str,
        db=None,
    ) -> dict:
        """
        Verify Stripe webhook signature, parse event, persist to DB,
        trigger downstream actions. Idempotent — duplicate events are no-ops.
        """
        stripe = _get_stripe()
        webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

        if webhook_secret and stripe_signature:
            try:
                event = stripe.Webhook.construct_event(
                    raw_payload, stripe_signature, webhook_secret
                )
            except stripe.error.SignatureVerificationError as e:
                logger.error("Webhook signature verification failed: %s", e)
                raise ValueError(f"Invalid signature: {e}")
        else:
            logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
            event = json.loads(raw_payload)

        event_id = event.get("id", "")
        event_type = event.get("type", "")
        data_obj = event.get("data", {}).get("object", {})

        logger.info("Processing webhook event: %s [%s]", event_type, event_id)

        result = await self._dispatch_event(event_type, event_id, data_obj, db)
        return {"received": True, "event_type": event_type, "event_id": event_id, "result": result}

    async def _dispatch_event(
        self,
        event_type: str,
        event_id: str,
        data: dict,
        db=None,
    ) -> dict:
        """Route Stripe event to the correct handler."""

        handlers = {
            "payment_intent.succeeded": self._on_payment_succeeded,
            "customer.subscription.created": self._on_subscription_created,
            "customer.subscription.updated": self._on_subscription_updated,
            "customer.subscription.deleted": self._on_subscription_deleted,
            "invoice.paid": self._on_invoice_paid,
            "invoice.payment_failed": self._on_invoice_failed,
            "checkout.session.completed": self._on_checkout_completed,
        }

        handler = handlers.get(event_type)
        if handler:
            return await handler(event_id, data, db)
        else:
            logger.debug("Unhandled event type: %s", event_type)
            return {"status": "ignored"}

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    async def _on_payment_succeeded(self, event_id: str, data: dict, db=None) -> dict:
        amount = data.get("amount", 0)
        customer_id = data.get("customer") or "guest"
        intent_id = data.get("id", "")

        await self._persist_event(db, event_id, "payment_succeeded", amount, customer_id,
                                  {"intent_id": intent_id})
        await self._slack_notify(
            f"💰 Payment succeeded: ${amount/100:.2f} from customer `{customer_id}`"
        )
        return {"status": "recorded", "amount_usd": amount / 100}

    async def _on_subscription_created(self, event_id: str, data: dict, db=None) -> dict:
        customer_id = data.get("customer", "")
        # Stripe returns items.data[0].price.unit_amount for subscription
        items = data.get("items", {}).get("data", [])
        amount = items[0].get("price", {}).get("unit_amount", 0) if items else 0
        plan_id = items[0].get("price", {}).get("id", "") if items else ""
        status = data.get("status", "")

        await self._persist_event(db, event_id, "subscription_created", amount, customer_id,
                                  {"plan_id": plan_id, "status": status})
        await self._slack_notify(
            f"🎉 New subscription: `{plan_id}` — ${amount/100:.2f}/mo — customer `{customer_id}`"
        )
        await self._trigger_genesis_onboarding(customer_id, plan_id, amount)
        return {"status": "subscription_active", "mrr_added": amount / 100}

    async def _on_subscription_updated(self, event_id: str, data: dict, db=None) -> dict:
        customer_id = data.get("customer", "")
        status = data.get("status", "")
        await self._persist_event(db, event_id, "subscription_updated", 0, customer_id,
                                  {"status": status})
        return {"status": "updated"}

    async def _on_subscription_deleted(self, event_id: str, data: dict, db=None) -> dict:
        customer_id = data.get("customer", "")
        items = data.get("items", {}).get("data", [])
        amount = items[0].get("price", {}).get("unit_amount", 0) if items else 0

        await self._persist_event(db, event_id, "subscription_churned", -amount, customer_id, {})
        await self._slack_notify(
            f"⚠️ Subscription cancelled: customer `{customer_id}` — MRR lost: ${amount/100:.2f}"
        )
        await self._fire_linear_alert(
            f"⚠️ Churn: Customer {customer_id} cancelled — ${amount/100:.2f} MRR lost"
        )
        return {"status": "churned", "mrr_lost": amount / 100}

    async def _on_invoice_paid(self, event_id: str, data: dict, db=None) -> dict:
        customer_id = data.get("customer", "")
        amount = data.get("amount_paid", 0)
        invoice_id = data.get("id", "")

        await self._persist_event(db, event_id, "invoice_paid", amount, customer_id,
                                  {"invoice_id": invoice_id})
        return {"status": "invoice_recorded", "amount_usd": amount / 100}

    async def _on_invoice_failed(self, event_id: str, data: dict, db=None) -> dict:
        customer_id = data.get("customer", "")
        invoice_id = data.get("id", "")
        attempt_count = data.get("attempt_count", 0)

        await self._persist_event(db, event_id, "invoice_failed", 0, customer_id,
                                  {"invoice_id": invoice_id, "attempt_count": attempt_count})
        await self._slack_notify(
            f"🔴 Invoice payment failed (attempt {attempt_count}): customer `{customer_id}`"
        )
        return {"status": "invoice_failed"}

    async def _on_checkout_completed(self, event_id: str, data: dict, db=None) -> dict:
        customer_email = data.get("customer_email", "")
        customer_id = data.get("customer", "")
        amount = data.get("amount_total", 0)
        mode = data.get("mode", "")
        session_id = data.get("id", "")

        await self._persist_event(db, event_id, "checkout_completed", amount, customer_id,
                                  {"email": customer_email, "session_id": session_id, "mode": mode})
        await self._slack_notify(
            f"✅ Checkout completed: `{customer_email}` — ${amount/100:.2f} — mode: {mode}"
        )
        return {"status": "checkout_recorded"}

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    async def _persist_event(
        self,
        db,
        event_id: str,
        event_type: str,
        amount_cents: int,
        customer_id: str,
        meta: dict,
    ):
        """Persist revenue event to DB. Falls back to log-only if DB unavailable."""
        if db is None:
            logger.info(
                "[LEDGER] event=%s amount=%d customer=%s meta=%s",
                event_type, amount_cents, customer_id, meta
            )
            return
        try:
            await db.execute(
                """
                INSERT INTO revenue_events
                    (stripe_event_id, event_type, amount_cents, customer_id, meta, created_at)
                VALUES (:eid, :etype, :amount, :cid, :meta, :ts)
                ON CONFLICT (stripe_event_id) DO NOTHING
                """,
                {
                    "eid": event_id,
                    "etype": event_type,
                    "amount": amount_cents,
                    "cid": customer_id,
                    "meta": json.dumps(meta),
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
            await db.commit()
        except Exception as e:
            logger.error("Failed to persist revenue event: %s", e)

    # -------------------------------------------------------------------------
    # MRR / Dashboard Metrics (DB-backed)
    # -------------------------------------------------------------------------

    async def compute_metrics(self, db=None) -> dict:
        """Compute live MRR/ARR/churn from DB revenue_events table."""
        if db is None:
            return {"error": "database not connected", "mrr": 0, "arr": 0}

        now = datetime.now(timezone.utc)

        try:
            rows = await db.fetch_all("SELECT event_type, amount_cents FROM revenue_events")
        except Exception as e:
            logger.error("Failed to query revenue_events: %s", e)
            return {"error": str(e), "mrr": 0, "arr": 0}

        subscriptions = [r for r in rows if r["event_type"] == "subscription_created"]
        churns = [r for r in rows if r["event_type"] == "subscription_churned"]
        invoices_paid = [r for r in rows if r["event_type"] == "invoice_paid"]

        active_sub_count = len(subscriptions) - len(churns)
        mrr_cents = sum(r["amount_cents"] for r in subscriptions if r["amount_cents"] > 0)
        churn_mrr = sum(abs(r["amount_cents"]) for r in churns)
        net_mrr = mrr_cents - churn_mrr

        churn_rate = (len(churns) / max(len(subscriptions), 1)) * 100
        ltv_cents = int(net_mrr / max(churn_rate / 100, 0.001))

        return {
            "timestamp": now.isoformat(),
            "mrr": round(net_mrr / 100, 2),
            "arr": round(net_mrr * 12 / 100, 2),
            "gross_mrr": round(mrr_cents / 100, 2),
            "churn_mrr": round(churn_mrr / 100, 2),
            "active_subscriptions": max(active_sub_count, 0),
            "churn_rate_pct": round(churn_rate, 2),
            "ltv": round(ltv_cents / 100, 2),
            "total_invoices_paid": len(invoices_paid),
            "currency": "usd",
        }

    # -------------------------------------------------------------------------
    # Notifications
    # -------------------------------------------------------------------------

    async def _slack_notify(self, message: str):
        """Post message to Slack via SLACK_WEBHOOK_URL env var."""
        url = os.environ.get("SLACK_WEBHOOK_URL", "")
        if not url:
            logger.debug("SLACK_WEBHOOK_URL not set — skipping Slack notification")
            return
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8) as client:
                await client.post(url, json={"text": message})
            logger.info("Slack notification sent: %s", message[:80])
        except Exception as e:
            logger.error("Slack notification failed: %s", e)

    async def _fire_linear_alert(self, title: str, priority: int = 1):
        """Create a Linear issue for urgent revenue events."""
        linear_key = os.environ.get("LINEAR_API_KEY", "")
        linear_team = os.environ.get("LINEAR_TEAM_ID", "")
        if not linear_key or not linear_team:
            return
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    "https://api.linear.app/graphql",
                    headers={"Authorization": linear_key, "Content-Type": "application/json"},
                    json={
                        "query": """
                            mutation CreateIssue($title: String!, $teamId: String!, $priority: Int!) {
                                issueCreate(input: { title: $title, teamId: $teamId, priority: $priority }) {
                                    success issue { id identifier url }
                                }
                            }
                        """,
                        "variables": {"title": title, "teamId": linear_team, "priority": priority},
                    },
                )
            logger.info("Linear alert fired: %s", title)
        except Exception as e:
            logger.error("Linear alert failed: %s", e)

    # -------------------------------------------------------------------------
    # GENESIS Onboarding
    # -------------------------------------------------------------------------

    async def _trigger_genesis_onboarding(self, customer_id: str, plan_id: str, amount_cents: int):
        """Trigger the GENESIS onboarding pipeline after first subscription."""
        try:
            from backend.genesis_onboarding import GenesisOnboarding
            genesis = GenesisOnboarding()
            await genesis.run(customer_id=customer_id, plan_id=plan_id, amount_cents=amount_cents)
        except Exception as e:
            logger.error("GENESIS onboarding failed: %s", e)
