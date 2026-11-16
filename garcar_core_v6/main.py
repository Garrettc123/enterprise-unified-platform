"""Garcar Enterprise v6.0 event gateway.

This is an isolated, fail-closed service. It does not perform delivery itself:
successful payments enqueue a durable outbox event for a separately supervised worker.
"""
from __future__ import annotations

import hmac
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import asyncpg
import stripe
from fastapi import FastAPI, Header, HTTPException, Query, Request

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("garcar_core_v6")

_pool: asyncpg.Pool | None = None
MAX_STRIPE_WEBHOOK_BYTES = 1_048_576


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def _format_usd_cents(cents: int) -> str:
    """Format a nonnegative integer-cent amount without floating-point rounding."""
    if cents < 0:
        raise ValueError("USD cents must be nonnegative")
    return f"{cents // 100}.{cents % 100:02d}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    database_url = _required_env("DATABASE_URL")
    webhook_secret = _required_env("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret.startswith("whsec_"):
        raise RuntimeError("STRIPE_WEBHOOK_SECRET does not look like a Stripe webhook secret")
    live_mode_setting = _required_env("STRIPE_EXPECT_LIVE").lower()
    if live_mode_setting not in {"true", "false"}:
        raise RuntimeError("STRIPE_EXPECT_LIVE must be exactly true or false")
    stripe_expected_live = live_mode_setting == "true"
    # No fallback credentials and no silent startup without the database.
    _pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=int(os.getenv("DB_POOL_MIN_SIZE", "1")),
        max_size=int(os.getenv("DB_POOL_MAX_SIZE", "5")),
        command_timeout=30,
    )
    try:
        async with _pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            schema_ready = await conn.fetchval(
                """
                SELECT
                  to_regclass('public.garcar_v6_customers') IS NOT NULL
                  AND to_regclass('public.garcar_v6_offers') IS NOT NULL
                  AND to_regclass('public.garcar_v6_opportunities') IS NOT NULL
                  AND to_regclass('public.garcar_v6_agreements') IS NOT NULL
                  AND to_regclass('public.garcar_v6_orders') IS NOT NULL
                  AND to_regclass('public.garcar_v6_payments') IS NOT NULL
                  AND to_regclass('public.garcar_v6_delivery_jobs') IS NOT NULL
                  AND to_regclass('public.garcar_v6_exceptions') IS NOT NULL
                  AND to_regclass('public.garcar_v6_stripe_events') IS NOT NULL
                  AND to_regclass('public.garcar_v6_outbox') IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_outbox'
                      AND column_name='lease_token'
                  )
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_outbox'
                      AND column_name='dead_lettered_at'
                  )
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_agreements'
                      AND column_name='agreed_price_cents'
                  )
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_agreements'
                      AND column_name='offer_version'
                  )
                  AND EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname='public'
                      AND tablename='garcar_v6_orders'
                      AND indexname='idx_garcar_v6_orders_agreement_unique'
                  )
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_exceptions'
                      AND column_name='stripe_event_id'
                  )
                  AND EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON t.oid=e.enumtypid
                    WHERE t.typname='garcar_v6_process_stage'
                      AND e.enumlabel='fulfillment_queued'
                  )
                  AND EXISTS (
                    SELECT 1 FROM pg_constraint c
                    JOIN pg_class r ON r.oid=c.conrelid
                    WHERE r.relname='garcar_v6_stripe_events'
                      AND c.conname='garcar_v6_stripe_events_status_check'
                      AND pg_get_constraintdef(c.oid) LIKE '%held_for_review%'
                  )
                """
            )
        if not schema_ready:
            raise RuntimeError("Garcar v6 schema is not installed; apply schema.sql to the dedicated database")
        app.state.stripe_webhook_secret = webhook_secret
        app.state.stripe_expected_live = stripe_expected_live
        logger.info("Garcar v6 started; database, schema, and Stripe mode verified")
        yield
    finally:
        if _pool is not None:
            await _pool.close()
            _pool = None
        logger.info("Garcar v6 stopped")


app = FastAPI(
    title="Garcar Enterprise v6.0 Core",
    version="6.0.0",
    description="Idempotent Stripe event gateway with a transactional fulfillment outbox.",
    lifespan=lifespan,
)


def _stripe_event(payload: bytes, signature: str | None, secret: str) -> dict[str, Any]:
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=secret,
            tolerance=300,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        logger.warning("Stripe webhook rejected: invalid payload or signature")
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook") from exc
    return dict(event)


async def _record_ignored(conn: asyncpg.Connection, event_id: str, event_type: str) -> None:
    # The receipt is inserted earlier in this same transaction; update it instead
    # of attempting a conflicting insert that would leave status='processed'.
    await conn.execute(
        """
        UPDATE garcar_v6_stripe_events
        SET status='ignored', event_type=$2
        WHERE stripe_event_id=$1
        """,
        event_id,
        event_type,
    )


async def _read_limited_body(request: Request) -> bytes:
    """Read a Stripe request body with a hard byte cap, including chunked requests."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header") from exc
        if declared_length < 0:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header")
        if declared_length > MAX_STRIPE_WEBHOOK_BYTES:
            raise HTTPException(status_code=413, detail="Stripe webhook body is too large")

    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > MAX_STRIPE_WEBHOOK_BYTES:
            raise HTTPException(status_code=413, detail="Stripe webhook body is too large")
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/webhooks/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database is not ready")

    payload = await _read_limited_body(request)
    event = _stripe_event(
        payload,
        stripe_signature,
        request.app.state.stripe_webhook_secret,
    )
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="Stripe event is missing required fields")
    event_livemode = event.get("livemode")
    if (
        not isinstance(event_livemode, bool)
        or event_livemode != request.app.state.stripe_expected_live
    ):
        logger.error("Stripe event %s rejected due to live/test mode mismatch", event_id)
        raise HTTPException(status_code=400, detail="Stripe event mode does not match configured endpoint")

    supported = {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }
    async with _pool.acquire() as conn:
        # Serialize deliveries for a Stripe event ID. The event receipt and all
        # associated financial writes commit together; a failed transaction is retryable.
        async with conn.transaction():
            inserted = await conn.fetchval(
                """
                INSERT INTO garcar_v6_stripe_events(stripe_event_id, event_type, status)
                VALUES($1, $2, 'processed')
                ON CONFLICT (stripe_event_id) DO NOTHING
                RETURNING stripe_event_id
                """,
                event_id,
                event_type,
            )
            if not inserted:
                return {"status": "duplicate_event", "event_id": event_id}

            if event_type not in supported:
                await conn.execute(
                    "UPDATE garcar_v6_stripe_events SET status='ignored' WHERE stripe_event_id=$1",
                    event_id,
                )
                return {"status": "ignored", "event_type": event_type}

            event_data = event.get("data") or {}
            session = event_data.get("object", {}) if hasattr(event_data, "get") else {}
            if not hasattr(session, "get") or session.get("object") != "checkout.session":
                await _record_ignored(conn, event_id, event_type)
                return {"status": "ignored", "reason": "unexpected_object"}

            # A completed Checkout session may still be unpaid for delayed payment methods.
            if session.get("payment_status") != "paid":
                await conn.execute(
                    "UPDATE garcar_v6_stripe_events SET status='ignored' WHERE stripe_event_id=$1",
                    event_id,
                )
                return {"status": "ignored", "reason": "payment_not_settled"}

            metadata = session.get("metadata") or {}
            if not hasattr(metadata, "get"):
                metadata = {}
            opportunity_raw = metadata.get("opportunity_id")
            customer_raw = metadata.get("customer_id")
            payment_intent_value = session.get("payment_intent")
            payment_intent = (
                payment_intent_value.get("id")
                if hasattr(payment_intent_value, "get")
                else payment_intent_value
            )
            amount = session.get("amount_total")
            currency = str(session.get("currency") or "").lower()

            try:
                opportunity_id = UUID(str(opportunity_raw))
                customer_id = UUID(str(customer_raw))
            except (ValueError, TypeError, AttributeError):
                await conn.execute(
                    """
                    INSERT INTO garcar_v6_exceptions(
                      related_entity_id, stripe_event_id, severity, module_source, error_message
                    )
                    VALUES(gen_random_uuid(), $1, 'high', 'stripe_webhook',
                           'Checkout session missing valid opportunity_id/customer_id metadata')
                    """,
                    event_id,
                )
                await conn.execute(
                    "UPDATE garcar_v6_stripe_events SET status='held_for_review' WHERE stripe_event_id=$1",
                    event_id,
                )
                return {"status": "held_for_review", "reason": "invalid_metadata", "event_id": event_id}

            if (
                not isinstance(payment_intent, str)
                or not payment_intent
                or not isinstance(amount, int)
                or isinstance(amount, bool)
                or amount < 0
                or not currency
            ):
                await conn.execute(
                    """
                    INSERT INTO garcar_v6_exceptions(
                      related_entity_id, stripe_event_id, severity, module_source, error_message
                    )
                    VALUES($1, $2, 'high', 'stripe_webhook', $3)
                    """,
                    opportunity_id,
                    event_id,
                    "Checkout session missing payment intent, amount, or currency",
                )
                await conn.execute(
                    "UPDATE garcar_v6_stripe_events SET status='held_for_review' WHERE stripe_event_id=$1",
                    event_id,
                )
                return {"status": "held_for_review", "reason": "missing_payment_fields", "event_id": event_id}

            # Serialize distinct Stripe event IDs that refer to the same PaymentIntent.
            # The order-table unique constraint remains the final idempotency backstop.
            await conn.fetchval(
                "SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))",
                str(payment_intent),
            )
            existing = await conn.fetchrow(
                "SELECT id FROM garcar_v6_orders WHERE stripe_payment_intent_id=$1",
                str(payment_intent),
            )
            if existing:
                await conn.execute(
                    "UPDATE garcar_v6_stripe_events SET status='ignored' WHERE stripe_event_id=$1",
                    event_id,
                )
                return {"status": "duplicate_payment", "order_id": str(existing['id'])}

            match = await conn.fetchrow(
                """
                SELECT a.id AS agreement_id, o.customer_id, o.offer_id,
                       o.stage::text AS opportunity_stage,
                       a.terms_hash, a.agreed_price_cents, a.offer_version,
                       f.is_active, a.signed_at
                FROM garcar_v6_opportunities o
                JOIN garcar_v6_agreements a ON a.opportunity_id=o.id
                JOIN garcar_v6_offers f ON f.id=o.offer_id
                WHERE o.id=$1 AND o.customer_id=$2
                ORDER BY a.signed_at DESC NULLS LAST
                LIMIT 1
                FOR UPDATE OF o, a, f
                """,
                opportunity_id,
                customer_id,
            )
            if (
                not match
                or not match["signed_at"]
                or not match["is_active"]
                or match["opportunity_stage"] != "proposal_dispatched"
                or not re.fullmatch(r"[0-9a-fA-F]{64}", str(match["terms_hash"] or ""))
                or match["agreed_price_cents"] is None
                or match["offer_version"] is None
                or int(match["offer_version"]) < 1
                or int(match["agreed_price_cents"]) != amount
                or currency != "usd"
            ):
                await conn.execute(
                    """
                    INSERT INTO garcar_v6_exceptions(
                      related_entity_id, stripe_event_id, severity, module_source, error_message
                    )
                    VALUES($1, $2, 'high', 'stripe_webhook',
                           'Payment did not match a proposal-stage opportunity, signed agreement with locked price/version, active offer, customer, USD currency, and exact amount')
                    """,
                    opportunity_id,
                    event_id,
                )
                await conn.execute(
                    "UPDATE garcar_v6_stripe_events SET status='held_for_review' WHERE stripe_event_id=$1",
                    event_id,
                )
                logger.error("Payment event %s did not match the commercial record", event_id)
                return {"status": "held_for_review", "event_id": event_id}

            order_id = await conn.fetchval(
                """
                INSERT INTO garcar_v6_orders(
                  agreement_id, customer_id, amount_cents, stage, stripe_payment_intent_id
                )
                VALUES($1, $2, $3, 'payment_settled', $4)
                RETURNING id
                """,
                match["agreement_id"],
                customer_id,
                amount,
                str(payment_intent),
            )
            await conn.execute(
                """
                INSERT INTO garcar_v6_payments(
                  order_id, stripe_payment_intent_id, amount_received_cents,
                  currency, status, stripe_event_id
                )
                VALUES($1, $2, $3, $4, 'succeeded', $5)
                """,
                order_id,
                str(payment_intent),
                amount,
                currency,
                event_id,
            )
            job_id = await conn.fetchval(
                """
                INSERT INTO garcar_v6_delivery_jobs(order_id, stage, prerequisites_met)
                VALUES($1, 'fulfillment_queued', TRUE)
                RETURNING id
                """,
                order_id,
            )
            await conn.execute(
                """
                UPDATE garcar_v6_opportunities
                SET stage='payment_settled'
                WHERE id=$1
                """,
                opportunity_id,
            )
            await conn.execute(
                """
                INSERT INTO garcar_v6_outbox(event_type, aggregate_id, payload)
                VALUES('order.settled', $1, jsonb_build_object(
                  'order_id', $2::text,
                  'delivery_job_id', $3::text,
                  'stripe_event_id', $4
                ))
                """,
                order_id,
                str(order_id),
                str(job_id),
                event_id,
            )

    logger.info("Payment reconciled to order %s; fulfillment queued as %s", order_id, job_id)
    return {
        "status": "accepted",
        "order_id": str(order_id),
        "delivery_job_id": str(job_id),
        "fulfillment": "queued",
    }


@app.get("/health/live")
async def liveness():
    return {"status": "alive", "version": "6.0.0"}


@app.get("/health/ready")
async def readiness():
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database pool is not initialized")
    try:
        async with _pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            schema_ready = await conn.fetchval(
                """
                SELECT
                  to_regclass('public.garcar_v6_customers') IS NOT NULL
                  AND to_regclass('public.garcar_v6_offers') IS NOT NULL
                  AND to_regclass('public.garcar_v6_opportunities') IS NOT NULL
                  AND to_regclass('public.garcar_v6_agreements') IS NOT NULL
                  AND to_regclass('public.garcar_v6_orders') IS NOT NULL
                  AND to_regclass('public.garcar_v6_payments') IS NOT NULL
                  AND to_regclass('public.garcar_v6_delivery_jobs') IS NOT NULL
                  AND to_regclass('public.garcar_v6_exceptions') IS NOT NULL
                  AND to_regclass('public.garcar_v6_stripe_events') IS NOT NULL
                  AND to_regclass('public.garcar_v6_outbox') IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_outbox'
                      AND column_name='lease_token'
                  )
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_outbox'
                      AND column_name='dead_lettered_at'
                  )
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_agreements'
                      AND column_name='agreed_price_cents'
                  )
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_agreements'
                      AND column_name='offer_version'
                  )
                  AND EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname='public'
                      AND tablename='garcar_v6_orders'
                      AND indexname='idx_garcar_v6_orders_agreement_unique'
                  )
                  AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='garcar_v6_exceptions'
                      AND column_name='stripe_event_id'
                  )
                  AND EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON t.oid=e.enumtypid
                    WHERE t.typname='garcar_v6_process_stage'
                      AND e.enumlabel='fulfillment_queued'
                  )
                  AND EXISTS (
                    SELECT 1 FROM pg_constraint c
                    JOIN pg_class r ON r.oid=c.conrelid
                    WHERE r.relname='garcar_v6_stripe_events'
                      AND c.conname='garcar_v6_stripe_events_status_check'
                      AND pg_get_constraintdef(c.oid) LIKE '%held_for_review%'
                  )
                """
            )
        if not schema_ready:
            raise HTTPException(status_code=503, detail="Garcar v6 schema is not installed")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Readiness check failed")
        raise HTTPException(status_code=503, detail="Database readiness check failed") from exc
    return {"status": "ready", "database": "connected", "schema": "installed", "version": "6.0.0"}


@app.get("/owner/exceptions")
async def owner_exceptions(
    limit: int = Query(default=25, ge=1, le=100),
    x_owner_monitor_token: str | None = Header(default=None, alias="X-Owner-Monitor-Token"),
):
    """List open exceptions, including their Stripe event link, for owner review."""
    expected = os.getenv("OWNER_MONITOR_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="Owner monitor is not configured")
    if not x_owner_monitor_token or not hmac.compare_digest(x_owner_monitor_token, expected):
        raise HTTPException(status_code=403, detail="Owner monitor authorization failed")
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database is not ready")
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, related_entity_id, stripe_event_id, severity::text AS severity,
                   module_source, error_message, created_at
            FROM garcar_v6_exceptions
            WHERE resolved=FALSE
            ORDER BY CASE severity
              WHEN 'critical' THEN 0
              WHEN 'high' THEN 1
              WHEN 'medium' THEN 2
              ELSE 3
            END, created_at ASC
            LIMIT $1
            """,
            limit,
        )
    return {"count": len(rows), "open_exceptions": [dict(row) for row in rows]}


@app.get("/owner/ledger-summary")
async def ledger_summary(
    x_owner_monitor_token: str | None = Header(default=None, alias="X-Owner-Monitor-Token"),
):
    """Read-only owner summary, protected by a separate server-side monitoring token."""
    expected = os.getenv("OWNER_MONITOR_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="Owner monitor is not configured")
    if not x_owner_monitor_token or not hmac.compare_digest(x_owner_monitor_token, expected):
        raise HTTPException(status_code=403, detail="Owner monitor authorization failed")
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database is not ready")
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
              COALESCE((SELECT SUM(amount_received_cents) FROM garcar_v6_payments
                        WHERE status='succeeded'), 0) AS gross_collected_cents,
              (SELECT COUNT(*) FROM garcar_v6_delivery_jobs
                WHERE stage='fulfillment_in_progress') AS active_fulfillment_jobs,
              (SELECT COUNT(*) FROM garcar_v6_delivery_jobs
                WHERE stage='fulfillment_queued') AS queued_fulfillment_jobs,
              (SELECT COUNT(*) FROM garcar_v6_exceptions WHERE resolved=FALSE) AS open_exceptions,
              (SELECT COUNT(*) FROM garcar_v6_outbox
                WHERE processed_at IS NULL AND dead_lettered_at IS NULL) AS pending_outbox,
              (SELECT COUNT(*) FROM garcar_v6_outbox
                WHERE dead_lettered_at IS NOT NULL) AS dead_lettered_outbox
            """
        )
    return {
        "gross_collected_usd": _format_usd_cents(int(row["gross_collected_cents"])),
        "active_fulfillment_jobs": row["active_fulfillment_jobs"],
        "queued_fulfillment_jobs": row["queued_fulfillment_jobs"],
        "open_exceptions": row["open_exceptions"],
        "pending_outbox": row["pending_outbox"],
        "dead_lettered_outbox": row["dead_lettered_outbox"],
    }
