"""Unit and PostgreSQL-backed integration tests for the isolated v6 core."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from garcar_core_v6.main import MAX_STRIPE_WEBHOOK_BYTES, _format_usd_cents, _required_env, _stripe_event, app, ledger_summary
from garcar_core_v6.outbox_worker import _dispatch_one, _retry_delay, _validate_sink_url, _claim_batch

# Synthetic test credentials are assembled from fragments to avoid resembling real secrets.
TEST_SECRET = "wh" + "sec" + "_" + "v6_test_" + "signature_material_for_tests_only"
OWNER_TEST_TOKEN = "owner_" + "monitor_" + "unit_test_token_for_v6"
SINK_TEST_TOKEN = "sink_" + "test_token_for_v6_worker_integration"


def test_usd_cents_format_uses_exact_integer_arithmetic() -> None:
    cases = {
        0: "0.00",
        1: "0.01",
        49700: "497.00",
        1234567890123456789: "12345678901234567.89",
    }
    for cents, expected in cases.items():
        assert _format_usd_cents(cents) == expected


def test_required_env_rejects_missing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GARCAR_TEST_REQUIRED", raising=False)
    with pytest.raises(RuntimeError, match="GARCAR_TEST_REQUIRED"):
        _required_env("GARCAR_TEST_REQUIRED")


def test_required_env_trims_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARCAR_TEST_REQUIRED", "  configured  ")
    assert _required_env("GARCAR_TEST_REQUIRED") == "configured"


def test_stripe_event_rejects_missing_signature() -> None:
    with pytest.raises(HTTPException) as exc:
        _stripe_event(b"{}", None, TEST_SECRET)
    assert exc.value.status_code == 400


def test_stripe_event_verifies_official_signature() -> None:
    now = int(time.time())
    event = {
        "id": "evt_v6_unit_signed",
        "object": "event",
        "api_version": "2024-06-20",
        "created": now,
        "data": {"object": {"id": "cus_v6_unit", "object": "customer"}},
        "livemode": False,
        "pending_webhooks": 1,
        "request": {"id": None, "idempotency_key": None},
        "type": "customer.created",
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    signed_payload = str(now).encode() + b"." + body
    digest = hmac.new(TEST_SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()
    signature = f"t={now},v1={digest}"

    result = _stripe_event(body, signature, TEST_SECRET)
    assert result["id"] == "evt_v6_unit_signed"
    assert result["type"] == "customer.created"


def test_stripe_event_rejects_tampered_payload() -> None:
    now = int(time.time())
    body = b'{"id":"evt_tampered","object":"event","type":"customer.created","data":{"object":{}}}'
    signature = f"t={now},v1=" + ("0" * 64)
    with pytest.raises(HTTPException) as exc:
        _stripe_event(body, signature, TEST_SECRET)
    assert exc.value.status_code == 400


def test_oversized_webhook_is_rejected_before_signature_parsing(db_client: TestClient) -> None:
    response = db_client.post(
        "/webhooks/stripe",
        content=b"x" * (MAX_STRIPE_WEBHOOK_BYTES + 1),
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Stripe webhook body is too large"


def test_outbox_retry_delay_grows_and_is_bounded() -> None:
    assert _retry_delay(1) == 5
    assert _retry_delay(2) == 10
    assert _retry_delay(12) == 3600
    assert _retry_delay(999) == 3600


def test_sink_url_requires_https_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FULFILLMENT_SINK_ALLOW_HTTP_LOOPBACK", raising=False)
    assert _validate_sink_url("https://fulfillment.example/events") == "https://fulfillment.example/events"
    with pytest.raises(RuntimeError, match="HTTPS"):
        _validate_sink_url("http://fulfillment.example/events")
    with pytest.raises(RuntimeError, match="userinfo"):
        _validate_sink_url("https://user:password@fulfillment.example/events")


def test_loopback_http_sink_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FULFILLMENT_SINK_ALLOW_HTTP_LOOPBACK", "true")
    assert _validate_sink_url("http://127.0.0.1:9000/events") == "http://127.0.0.1:9000/events"
    with pytest.raises(RuntimeError, match="HTTPS"):
        _validate_sink_url("http://example.test/events")


def test_owner_ledger_fails_closed_without_configured_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OWNER_MONITOR_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ledger_summary())
    assert exc.value.status_code == 503


def test_owner_ledger_rejects_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OWNER_MONITOR_TOKEN", OWNER_TEST_TOKEN)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ledger_summary("wrong-token"))
    assert exc.value.status_code == 403


def _test_database_url() -> str:
    url = os.getenv("GARCAR_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("PostgreSQL integration tests require GARCAR_TEST_DATABASE_URL")
    return url


async def _reset_database(url: str) -> None:
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(
            """
            TRUNCATE TABLE
              garcar_v6_outbox,
              garcar_v6_stripe_events,
              garcar_v6_exceptions,
              garcar_v6_artifacts,
              garcar_v6_bank_matches,
              garcar_v6_payouts,
              garcar_v6_delivery_jobs,
              garcar_v6_payments,
              garcar_v6_orders,
              garcar_v6_agreements,
              garcar_v6_opportunities,
              garcar_v6_offers,
              garcar_v6_customers,
              garcar_v6_organizations
            RESTART IDENTITY CASCADE
            """
        )
    finally:
        await conn.close()


async def _seed_signed_opportunity(url: str, price_cents: int = 49700) -> dict[str, str]:
    conn = await asyncpg.connect(url)
    try:
        customer_id = await conn.fetchval(
            "INSERT INTO garcar_v6_customers(email, name) VALUES($1, $2) RETURNING id",
            f"v6-test-{time.time_ns()}@example.test",
            "CI test customer",
        )
        offer_id = await conn.fetchval(
            """
            INSERT INTO garcar_v6_offers(name, fixed_price_cents, delivery_template_id, is_active)
            VALUES('CI test offer', $1, 'ci-template', TRUE) RETURNING id
            """,
            price_cents,
        )
        opportunity_id = await conn.fetchval(
            """
            INSERT INTO garcar_v6_opportunities(customer_id, offer_id, stage)
            VALUES($1, $2, 'proposal_dispatched') RETURNING id
            """,
            customer_id,
            offer_id,
        )
        await conn.execute(
            """
            INSERT INTO garcar_v6_agreements(
              opportunity_id, terms_hash, agreed_price_cents, offer_version, signed_at
            )
            VALUES($1, $2, $3, 1, CURRENT_TIMESTAMP)
            """,
            opportunity_id,
            "a" * 64,
            price_cents,
        )
        return {"customer_id": str(customer_id), "opportunity_id": str(opportunity_id)}
    finally:
        await conn.close()


def _signed_stripe_payload(
    event_id: str,
    session: dict[str, Any] | None,
    *,
    livemode: bool = False,
) -> tuple[bytes, str]:
    now = int(time.time())
    event = {
        "id": event_id,
        "object": "event",
        "api_version": "2024-06-20",
        "created": now,
        "data": {"object": session},
        "livemode": livemode,
        "pending_webhooks": 1,
        "request": {"id": None, "idempotency_key": None},
        "type": "checkout.session.completed",
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    signed_payload = str(now).encode() + b"." + body
    digest = hmac.new(TEST_SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()
    return body, f"t={now},v1={digest}"


@pytest.fixture
def db_client(monkeypatch: pytest.MonkeyPatch):
    url = _test_database_url()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    monkeypatch.setenv("STRIPE_EXPECT_LIVE", "false")
    monkeypatch.setenv("OWNER_MONITOR_TOKEN", OWNER_TEST_TOKEN)
    asyncio.run(_reset_database(url))
    with TestClient(app) as client:
        yield client


def test_paid_checkout_is_idempotent_and_queues_fulfillment(db_client: TestClient) -> None:
    url = _test_database_url()
    ids = asyncio.run(_seed_signed_opportunity(url))
    session = {
        "id": "cs_v6_ci_paid",
        "object": "checkout.session",
        "payment_status": "paid",
        "metadata": ids,
        "payment_intent": "pi_v6_ci_idempotent",
        "amount_total": 49700,
        "currency": "usd",
    }
    body, signature = _signed_stripe_payload("evt_v6_ci_paid", session)
    first = db_client.post("/webhooks/stripe", content=body, headers={"Stripe-Signature": signature})
    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    assert first.json()["fulfillment"] == "queued"

    duplicate = db_client.post("/webhooks/stripe", content=body, headers={"Stripe-Signature": signature})
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "duplicate_event"

    other_event_body, other_signature = _signed_stripe_payload("evt_v6_ci_same_payment", session)
    other_event = db_client.post(
        "/webhooks/stripe",
        content=other_event_body,
        headers={"Stripe-Signature": other_signature},
    )
    assert other_event.status_code == 200
    assert other_event.json()["status"] == "duplicate_payment"

    summary = db_client.get(
        "/owner/ledger-summary",
        headers={"X-Owner-Monitor-Token": OWNER_TEST_TOKEN},
    )
    assert summary.status_code == 200
    assert summary.json()["gross_collected_usd"] == "497.00"
    assert summary.json()["queued_fulfillment_jobs"] == 1
    assert summary.json()["active_fulfillment_jobs"] == 0
    assert summary.json()["pending_outbox"] == 1
    assert summary.json()["dead_lettered_outbox"] == 0

    async def counts() -> tuple[int, int, int]:
        conn = await asyncpg.connect(url)
        try:
            orders = await conn.fetchval("SELECT COUNT(*) FROM garcar_v6_orders")
            payments = await conn.fetchval("SELECT COUNT(*) FROM garcar_v6_payments")
            outbox = await conn.fetchval("SELECT COUNT(*) FROM garcar_v6_outbox")
            return orders, payments, outbox
        finally:
            await conn.close()

    assert asyncio.run(counts()) == (1, 1, 1)

    async def relay_outbox(url: str) -> tuple[bool, str, bool]:
        pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
        received: list[httpx.Request] = []

        def sink_handler(request: httpx.Request) -> httpx.Response:
            received.append(request)
            return httpx.Response(204)

        try:
            rows = await _claim_batch(pool, batch_size=10, lease_seconds=90)
            assert len(rows) == 1
            async with httpx.AsyncClient(transport=httpx.MockTransport(sink_handler)) as sink_client:
                ok = await _dispatch_one(
                    pool,
                    sink_client,
                    "https://sink.example/events",
                    SINK_TEST_TOKEN,
                    rows[0],
                )
            async with pool.acquire() as conn:
                processed = await conn.fetchval(
                    "SELECT processed_at IS NOT NULL FROM garcar_v6_outbox WHERE id=$1",
                    rows[0]["id"],
                )
            return ok, received[0].headers["Idempotency-Key"], bool(processed)
        finally:
            await pool.close()

    assert asyncio.run(relay_outbox(url)) == (True, "garcar-outbox-1", True)


def test_second_payment_intent_for_settled_opportunity_is_held_for_review(db_client: TestClient) -> None:
    url = _test_database_url()
    ids = asyncio.run(_seed_signed_opportunity(url))

    first_session = {
        "id": "cs_v6_ci_first_settlement",
        "object": "checkout.session",
        "payment_status": "paid",
        "metadata": ids,
        "payment_intent": "pi_v6_ci_first_settlement",
        "amount_total": 49700,
        "currency": "usd",
    }
    first_body, first_signature = _signed_stripe_payload("evt_v6_ci_first_settlement", first_session)
    first = db_client.post(
        "/webhooks/stripe",
        content=first_body,
        headers={"Stripe-Signature": first_signature},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "accepted"

    second_session = {
        "id": "cs_v6_ci_second_settlement",
        "object": "checkout.session",
        "payment_status": "paid",
        "metadata": ids,
        "payment_intent": "pi_v6_ci_second_settlement",
        "amount_total": 49700,
        "currency": "usd",
    }
    second_body, second_signature = _signed_stripe_payload("evt_v6_ci_second_settlement", second_session)
    second = db_client.post(
        "/webhooks/stripe",
        content=second_body,
        headers={"Stripe-Signature": second_signature},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "held_for_review"

    async def record_counts() -> tuple[int, int, int, int]:
        conn = await asyncpg.connect(url)
        try:
            orders = await conn.fetchval("SELECT COUNT(*) FROM garcar_v6_orders")
            payments = await conn.fetchval("SELECT COUNT(*) FROM garcar_v6_payments")
            outbox = await conn.fetchval("SELECT COUNT(*) FROM garcar_v6_outbox")
            exceptions = await conn.fetchval(
                "SELECT COUNT(*) FROM garcar_v6_exceptions WHERE stripe_event_id=$1",
                "evt_v6_ci_second_settlement",
            )
            return orders, payments, outbox, exceptions
        finally:
            await conn.close()

    assert asyncio.run(record_counts()) == (1, 1, 1, 1)


def test_outbox_dead_letters_after_max_attempts(db_client: TestClient) -> None:
    url = _test_database_url()

    async def exercise(url: str) -> tuple[bool, bool, int]:
        conn = await asyncpg.connect(url)
        try:
            aggregate_id = await conn.fetchval("SELECT gen_random_uuid()")
            outbox_id = await conn.fetchval(
                """
                INSERT INTO garcar_v6_outbox(event_type, aggregate_id, payload, attempts)
                VALUES('order.settled', $1, '{"order_id":"dead-letter-test"}'::jsonb, 11)
                RETURNING id
                """,
                aggregate_id,
            )
        finally:
            await conn.close()

        pool = await asyncpg.create_pool(url, min_size=1, max_size=2)

        def failing_sink(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        try:
            rows = await _claim_batch(pool, batch_size=10, lease_seconds=90)
            row = next(item for item in rows if int(item["id"]) == int(outbox_id))
            async with httpx.AsyncClient(transport=httpx.MockTransport(failing_sink)) as sink_client:
                delivered = await _dispatch_one(
                    pool,
                    sink_client,
                    "https://sink.example/events",
                    SINK_TEST_TOKEN,
                    row,
                )
            async with pool.acquire() as conn:
                dead_lettered = await conn.fetchval(
                    "SELECT dead_lettered_at IS NOT NULL FROM garcar_v6_outbox WHERE id=$1",
                    outbox_id,
                )
                exception_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM garcar_v6_exceptions WHERE module_source='outbox_worker'"
                )
            return delivered, bool(dead_lettered), int(exception_count)
        finally:
            await pool.close()

    assert asyncio.run(exercise(url)) == (False, True, 1)


def test_live_mode_mismatch_is_rejected_before_receipt(db_client: TestClient) -> None:
    body, signature = _signed_stripe_payload(
        "evt_v6_ci_wrong_mode",
        {
            "id": "cs_v6_ci_wrong_mode",
            "object": "checkout.session",
            "payment_status": "paid",
            "metadata": {},
            "payment_intent": "pi_v6_ci_wrong_mode",
            "amount_total": 49700,
            "currency": "usd",
        },
        livemode=True,
    )
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 400
    assert "mode" in response.json()["detail"].lower()

    async def receipt_count() -> int:
        conn = await asyncpg.connect(_test_database_url())
        try:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM garcar_v6_stripe_events WHERE stripe_event_id=$1",
                "evt_v6_ci_wrong_mode",
            )
        finally:
            await conn.close()

    assert asyncio.run(receipt_count()) == 0


def test_paid_event_without_metadata_is_linked_to_owner_exception(db_client: TestClient) -> None:
    event_id = "evt_v6_ci_bad_metadata"
    body, signature = _signed_stripe_payload(
        event_id,
        {
            "id": "cs_v6_ci_bad_metadata",
            "object": "checkout.session",
            "payment_status": "paid",
            "metadata": {},
            "payment_intent": "pi_v6_ci_bad_metadata",
            "amount_total": 49700,
            "currency": "usd",
        },
    )
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "held_for_review"
    assert response.json()["event_id"] == event_id

    review = db_client.get(
        "/owner/exceptions",
        headers={"X-Owner-Monitor-Token": OWNER_TEST_TOKEN},
    )
    assert review.status_code == 200
    assert review.json()["count"] == 1
    assert review.json()["open_exceptions"][0]["stripe_event_id"] == event_id
    assert review.json()["open_exceptions"][0]["module_source"] == "stripe_webhook"


def test_unexpected_checkout_object_is_recorded_as_ignored(db_client: TestClient) -> None:
    body, signature = _signed_stripe_payload(
        "evt_v6_ci_unexpected_object",
        {"id": "cus_wrong_object", "object": "customer"},
    )
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "reason": "unexpected_object"}

    async def event_status() -> str:
        conn = await asyncpg.connect(_test_database_url())
        try:
            return await conn.fetchval(
                "SELECT status FROM garcar_v6_stripe_events WHERE stripe_event_id=$1",
                "evt_v6_ci_unexpected_object",
            )
        finally:
            await conn.close()

    assert asyncio.run(event_status()) == "ignored"


def test_malformed_session_object_is_recorded_as_ignored(db_client: TestClient) -> None:
    body, signature = _signed_stripe_payload(
        "evt_v6_ci_null_session",
        None,  # type: ignore[arg-type]
    )
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "reason": "unexpected_object"}


def test_non_mapping_metadata_is_held_for_review(db_client: TestClient) -> None:
    body, signature = _signed_stripe_payload(
        "evt_v6_ci_bad_metadata_shape",
        {
            "id": "cs_v6_ci_bad_metadata_shape",
            "object": "checkout.session",
            "payment_status": "paid",
            "metadata": ["not", "a", "mapping"],
            "payment_intent": "pi_v6_ci_bad_metadata_shape",
            "amount_total": 49700,
            "currency": "usd",
        },
    )
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "held_for_review"


def test_unpaid_checkout_is_recorded_as_ignored(db_client: TestClient) -> None:
    body, signature = _signed_stripe_payload(
        "evt_v6_ci_unpaid",
        {
            "id": "cs_v6_ci_unpaid",
            "object": "checkout.session",
            "payment_status": "unpaid",
            "metadata": {},
            "payment_intent": None,
            "amount_total": 49700,
            "currency": "usd",
        },
    )
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "reason": "payment_not_settled"}

    async def event_status() -> str:
        conn = await asyncpg.connect(_test_database_url())
        try:
            return await conn.fetchval(
                "SELECT status FROM garcar_v6_stripe_events WHERE stripe_event_id=$1",
                "evt_v6_ci_unpaid",
            )
        finally:
            await conn.close()

    assert asyncio.run(event_status()) == "ignored"


def test_outbox_http_failure_schedules_retry(db_client: TestClient) -> None:
    url = _test_database_url()

    async def exercise(url: str) -> tuple[bool, int, bool, str | None]:
        conn = await asyncpg.connect(url)
        try:
            aggregate_id = await conn.fetchval("SELECT gen_random_uuid()")
            outbox_id = await conn.fetchval(
                """
                INSERT INTO garcar_v6_outbox(event_type, aggregate_id, payload)
                VALUES('order.settled', $1, '{"order_id":"retry-test"}'::jsonb)
                RETURNING id
                """,
                aggregate_id,
            )
        finally:
            await conn.close()

        pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
        try:
            rows = await _claim_batch(pool, batch_size=10, lease_seconds=90)
            row = next(item for item in rows if int(item["id"]) == int(outbox_id))

            def failing_sink(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(503)

            async with httpx.AsyncClient(transport=httpx.MockTransport(failing_sink)) as client:
                delivered = await _dispatch_one(
                    pool,
                    client,
                    "https://sink.example/events",
                    SINK_TEST_TOKEN,
                    row,
                )
            async with pool.acquire() as conn:
                state = await conn.fetchrow(
                    "SELECT attempts, available_at > CURRENT_TIMESTAMP, last_error FROM garcar_v6_outbox WHERE id=$1",
                    outbox_id,
                )
            return delivered, int(state["attempts"]), bool(state[1]), state["last_error"]
        finally:
            await pool.close()

    assert asyncio.run(exercise(url)) == (False, 1, True, "http_status_503")


def test_signed_agreement_price_is_not_changed_by_current_offer_edit(db_client: TestClient) -> None:
    url = _test_database_url()
    ids = asyncio.run(_seed_signed_opportunity(url))

    async def change_current_offer() -> None:
        conn = await asyncpg.connect(url)
        try:
            await conn.execute(
                """
                UPDATE garcar_v6_offers
                SET fixed_price_cents=99000, version=version+1
                WHERE id=(
                  SELECT offer_id FROM garcar_v6_opportunities WHERE id=$1
                )
                """,
                ids["opportunity_id"],
            )
        finally:
            await conn.close()

    asyncio.run(change_current_offer())
    session = {
        "id": "cs_v6_ci_locked_price",
        "object": "checkout.session",
        "payment_status": "paid",
        "metadata": ids,
        "payment_intent": "pi_v6_ci_locked_price",
        "amount_total": 49700,
        "currency": "usd",
    }
    body, signature = _signed_stripe_payload("evt_v6_ci_locked_price", session)
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_legacy_agreement_without_price_snapshot_is_held_for_review(db_client: TestClient) -> None:
    url = _test_database_url()
    ids = asyncio.run(_seed_signed_opportunity(url))

    async def clear_snapshot() -> None:
        conn = await asyncpg.connect(url)
        try:
            await conn.execute(
                """
                UPDATE garcar_v6_agreements
                SET agreed_price_cents=NULL, offer_version=NULL
                WHERE opportunity_id=$1
                """,
                ids["opportunity_id"],
            )
        finally:
            await conn.close()

    asyncio.run(clear_snapshot())
    session = {
        "id": "cs_v6_ci_legacy_agreement",
        "object": "checkout.session",
        "payment_status": "paid",
        "metadata": ids,
        "payment_intent": "pi_v6_ci_legacy_agreement",
        "amount_total": 49700,
        "currency": "usd",
    }
    body, signature = _signed_stripe_payload("evt_v6_ci_legacy_agreement", session)
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "held_for_review"


def test_malformed_terms_hash_is_held_for_review(db_client: TestClient) -> None:
    url = _test_database_url()
    ids = asyncio.run(_seed_signed_opportunity(url))

    async def alter_terms_hash() -> None:
        conn = await asyncpg.connect(url)
        try:
            await conn.execute(
                """
                UPDATE garcar_v6_agreements
                SET terms_hash='not-a-sha256-hash'
                WHERE opportunity_id=$1
                """,
                ids["opportunity_id"],
            )
        finally:
            await conn.close()

    asyncio.run(alter_terms_hash())
    session = {
        "id": "cs_v6_ci_bad_terms_hash",
        "object": "checkout.session",
        "payment_status": "paid",
        "metadata": ids,
        "payment_intent": "pi_v6_ci_bad_terms_hash",
        "amount_total": 49700,
        "currency": "usd",
    }
    body, signature = _signed_stripe_payload("evt_v6_ci_bad_terms_hash", session)
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "held_for_review"


def test_price_mismatch_is_held_for_review(db_client: TestClient) -> None:
    url = _test_database_url()
    ids = asyncio.run(_seed_signed_opportunity(url))
    session = {
        "id": "cs_v6_ci_mismatch",
        "object": "checkout.session",
        "payment_status": "paid",
        "metadata": ids,
        "payment_intent": "pi_v6_ci_mismatch",
        "amount_total": 49800,
        "currency": "usd",
    }
    body, signature = _signed_stripe_payload("evt_v6_ci_mismatch", session)
    response = db_client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "held_for_review"

    async def check_event_status() -> str:
        conn = await asyncpg.connect(url)
        try:
            return await conn.fetchval(
                "SELECT status FROM garcar_v6_stripe_events WHERE stripe_event_id=$1",
                "evt_v6_ci_mismatch",
            )
        finally:
            await conn.close()

    assert asyncio.run(check_event_status()) == "held_for_review"

    async def check_records() -> tuple[int, int]:
        conn = await asyncpg.connect(url)
        try:
            orders = await conn.fetchval("SELECT COUNT(*) FROM garcar_v6_orders")
            exceptions = await conn.fetchval("SELECT COUNT(*) FROM garcar_v6_exceptions WHERE resolved=FALSE")
            return orders, exceptions
        finally:
            await conn.close()

    assert asyncio.run(check_records()) == (0, 1)
