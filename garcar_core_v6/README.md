# Garcar Enterprise v6 Core Preview

This directory contains an isolated payment-event gateway preview. It does not replace the existing platform backend and it does not deliver customer work by itself.

## Current behavior

- Caps webhook request bodies at 1 MiB while streaming, verifies Stripe webhook signatures with the official Stripe SDK, and enforces a 300-second signature tolerance.
- Requires a paid Checkout Session, valid customer/opportunity metadata, a signed agreement, an active offer, the exact configured amount, and USD currency before recording a settled order.
- Stores Stripe event receipts, order/payment records, delivery-job records, and an outbox event in a PostgreSQL transaction.
- Prevents duplicate processing by Stripe event ID and payment-intent ID.
- Marks commercial mismatches for review instead of creating an order.
- Exposes liveness/readiness endpoints and a separately token-protected, read-only ledger summary.
- Marks new delivery jobs as `fulfillment_queued`. There is no worker in this preview, so queued jobs are not evidence that delivery has started or completed.

## Prerequisites

- Python 3.11 or later
- PostgreSQL with permission to create the isolated tables and the `pgcrypto` extension
- A Stripe webhook signing secret for the intended Stripe environment
- A dedicated, disposable database for local tests; do not point this preview at production data

## Configuration and local run

Set secrets in your protected shell/environment manager. Do not commit them to source control or paste them into logs.

```sh
# Inject values from your protected environment/secret manager; do not put them in source files.
: "${DATABASE_URL:?Set a native postgres:// or postgresql:// URI}"
: "${STRIPE_WEBHOOK_SECRET:?Set from the Stripe webhook secret manager}"
: "${STRIPE_EXPECT_LIVE:?Set false for sandbox/test or true for a live Stripe endpoint}"
: "${OWNER_MONITOR_TOKEN:?Set a unique random monitoring token}"
# Explicit opt-in: only after confirming this is a dedicated non-production database.
export GARCAR_ALLOW_SCHEMA_APPLY=true
```

Use a native `postgresql://` or `postgres://` URL accepted by asyncpg. The deployment script deliberately rejects SQLAlchemy-only `postgresql+asyncpg://` URLs. Schema application uses the same asyncpg driver as the service, and the database URI is read from the protected process environment rather than passed as a command-line argument.

Run from the repository root:

```sh
bash garcar_core_v6/deploy.sh
```

The service binds to `127.0.0.1:8000` by default. Set `HOST` and `PORT` explicitly only when the environment requires different binding. Do not expose the service publicly without a reviewed reverse-proxy/TLS, network policy, secret management, and deployment configuration.

Endpoints:
- `GET /health/live` — process liveness only.
- `GET /health/ready` — database and required-schema readiness.
- `POST /webhooks/stripe` — Stripe-signed webhook receiver.
- `GET /owner/ledger-summary` — read-only summary, requires `X-Owner-Monitor-Token`.
- `GET /owner/exceptions?limit=25` — authenticated listing of unresolved exceptions linked to Stripe event IDs where available.

## Run the durable outbox relay

The API and the relay are separate processes. The relay requires the same `DATABASE_URL` plus an operator-controlled downstream receiver:

```sh
export FULFILLMENT_SINK_URL='https://your-approved-receiver.example/events'
: "${FULFILLMENT_SINK_TOKEN:?Inject from your protected environment/secret manager}"
./garcar_core_v6/.venv/bin/python -m garcar_core_v6.outbox_worker
```

The relay claims rows with PostgreSQL leases and `SKIP LOCKED`, delivers them with the stable `Idempotency-Key` header, and marks an event processed only after a 2xx acknowledgement. It retries failures with bounded exponential backoff; after 12 failed attempts, it marks the row dead-lettered and creates an exception for review. The receiver must deduplicate by the supplied idempotency key because delivery is at-least-once. The relay forwards `order.settled` events; it does not create customer artifacts or verify customer acceptance.

The sink URL must use HTTPS. For local development only, HTTP is allowed for loopback addresses when `FULFILLMENT_SINK_ALLOW_HTTP_LOOPBACK=true`. Redirects are not followed, and the bearer token is not written to logs. Run the relay only against a reviewed downstream endpoint.

## Tests

Install development dependencies:

```sh
python -m pip install -r garcar_core_v6/requirements-dev.txt
python -m compileall -q garcar_core_v6 tests
bash -n garcar_core_v6/deploy.sh
pytest -q
```

The unit tests run without a database. PostgreSQL-backed integration tests run only when `GARCAR_TEST_DATABASE_URL` points to a disposable database with `garcar_core_v6/schema.sql` already applied. Those tests truncate the isolated v6 tables. Never set that variable to production or any database containing user data.

## Known limitations — not production-ready

- No durable outbox worker, retry scheduler, dead-letter/poison-message handling, or fulfillment implementation.
- No artifact builder, artifact integrity verification, or independent QA engine.
- No Stripe payout-to-bank reconciliation; the ledger summary is not bank-confirmed revenue.
- Payment validation requires a 64-character hexadecimal terms hash, the signed agreement's locked `agreed_price_cents`, and the recorded `offer_version`; a later edit to the current offer price does not rewrite signed terms. Legacy agreement rows without these fields are held for review. No complete customer-facing checkout/session-creation or agreement-signing flow is included, and refund/dispute handling, tax handling, and subscription lifecycle remain out of scope.
- No rate limiting, public-edge deployment hardening, observability integration, backup/restore procedure, or live operational runbook.
- Integration tests are meaningful checks, not proof of production readiness. Run them in CI and against an isolated PostgreSQL instance before any rollout.

No production database migration or deployment is performed by this project preview.
