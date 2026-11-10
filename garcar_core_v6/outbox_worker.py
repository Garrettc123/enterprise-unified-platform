"""At-least-once relay for the v6 transactional outbox.

This process forwards events to an operator-configured downstream service. It does
not itself generate artifacts or prove customer delivery; the receiver must honor
the supplied Idempotency-Key.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from urllib.parse import urlsplit

import asyncpg
import httpx

logger = logging.getLogger("garcar_core_v6.outbox_worker")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

MAX_ATTEMPTS = 12
MAX_BACKOFF_SECONDS = 3600
DEFAULT_POLL_SECONDS = 2.0
DEFAULT_BATCH_SIZE = 10
LEASE_SECONDS = 90


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def _validate_sink_url(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("FULFILLMENT_SINK_URL must be an absolute URL without userinfo, query, or fragment")
    if parsed.scheme == "https":
        return value
    host = parsed.hostname.lower()
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    allow_local_http = os.getenv("FULFILLMENT_SINK_ALLOW_HTTP_LOOPBACK", "").lower() == "true"
    if parsed.scheme == "http" and host in local_hosts and allow_local_http:
        return value
    raise RuntimeError(
        "FULFILLMENT_SINK_URL must use HTTPS; HTTP is allowed only for loopback when "
        "FULFILLMENT_SINK_ALLOW_HTTP_LOOPBACK=true"
    )


def _retry_delay(attempts: int) -> int:
    exponent = max(0, min(int(attempts) - 1, 10))
    return min(MAX_BACKOFF_SECONDS, 5 * (2**exponent))


async def _claim_batch(pool: asyncpg.Pool, batch_size: int, lease_seconds: int) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                WITH candidates AS (
                  SELECT id
                  FROM garcar_v6_outbox
                  WHERE processed_at IS NULL
                    AND dead_lettered_at IS NULL
                    AND available_at <= CURRENT_TIMESTAMP
                    AND (
                      locked_at IS NULL
                      OR locked_at < CURRENT_TIMESTAMP - ($1::double precision * INTERVAL '1 second')
                    )
                  ORDER BY id
                  LIMIT $2
                  FOR UPDATE SKIP LOCKED
                )
                UPDATE garcar_v6_outbox AS o
                SET locked_at=CURRENT_TIMESTAMP,
                    lease_token=gen_random_uuid(),
                    attempts=o.attempts+1,
                    last_error=NULL
                FROM candidates AS c
                WHERE o.id=c.id
                RETURNING o.id, o.event_type, o.aggregate_id, o.payload, o.created_at, o.attempts, o.lease_token
                """,
                lease_seconds,
                batch_size,
            )
    return [dict(row) for row in rows]


async def _mark_processed(pool: asyncpg.Pool, row: dict[str, Any]) -> bool:
    async with pool.acquire() as conn:
        command = await conn.execute(
            """
            UPDATE garcar_v6_outbox
            SET processed_at=CURRENT_TIMESTAMP, locked_at=NULL, lease_token=NULL, last_error=NULL
            WHERE id=$1 AND lease_token=$2 AND processed_at IS NULL AND dead_lettered_at IS NULL
            """,
            int(row["id"]),
            row["lease_token"],
        )
    return command.endswith(" 1")


async def _mark_failed(
    pool: asyncpg.Pool,
    row: dict[str, Any],
    reason: str,
) -> None:
    outbox_id = int(row["id"])
    attempts = int(row["attempts"])
    reason = reason[:300]
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchrow(
                """
                SELECT processed_at, dead_lettered_at, lease_token
                FROM garcar_v6_outbox
                WHERE id=$1
                FOR UPDATE
                """,
                outbox_id,
            )
            if (
                not current
                or current["processed_at"] is not None
                or current["dead_lettered_at"] is not None
                or current["lease_token"] != row["lease_token"]
            ):
                return

            if attempts >= MAX_ATTEMPTS:
                await conn.execute(
                    """
                    INSERT INTO garcar_v6_exceptions(
                      related_entity_id, severity, module_source, error_message
                    )
                    VALUES($1, 'high', 'outbox_worker', $2)
                    """,
                    row["aggregate_id"],
                    f"Outbox event {outbox_id} was dead-lettered after {attempts} attempts ({reason})",
                )
                await conn.execute(
                    """
                    UPDATE garcar_v6_outbox
                    SET dead_lettered_at=CURRENT_TIMESTAMP, locked_at=NULL, lease_token=NULL,
                        last_error=$2, available_at=CURRENT_TIMESTAMP
                    WHERE id=$1 AND lease_token=$3 AND processed_at IS NULL
                    """,
                    outbox_id,
                    reason,
                    row["lease_token"],
                )
                logger.error("Outbox event %s dead-lettered after %s attempts", outbox_id, attempts)
                return

            delay = _retry_delay(attempts)
            await conn.execute(
                """
                UPDATE garcar_v6_outbox
                SET locked_at=NULL, lease_token=NULL,
                    available_at=CURRENT_TIMESTAMP + ($2::double precision * INTERVAL '1 second'),
                    last_error=$3
                WHERE id=$1 AND lease_token=$4 AND processed_at IS NULL AND dead_lettered_at IS NULL
                """,
                outbox_id,
                delay,
                reason,
                row["lease_token"],
            )
            logger.warning(
                "Outbox delivery failed id=%s attempt=%s; retry scheduled in %ss (%s)",
                outbox_id,
                attempts,
                delay,
                reason,
            )


async def _dispatch_one(
    pool: asyncpg.Pool,
    client: httpx.AsyncClient,
    sink_url: str,
    sink_token: str,
    row: dict[str, Any],
) -> bool:
    outbox_id = int(row["id"])
    payload = row["payload"]
    try:
        if isinstance(payload, str):
            payload = json.loads(payload)
        envelope = {
            "outbox_id": outbox_id,
            "event_type": row["event_type"],
            "aggregate_id": str(row["aggregate_id"]),
            "payload": payload,
            "created_at": row["created_at"].isoformat(),
            "attempt": int(row["attempts"]),
        }
        response = await client.post(
            sink_url,
            json=envelope,
            headers={
                "Authorization": f"Bearer {sink_token}",
                "Content-Type": "application/json",
                "Idempotency-Key": f"garcar-outbox-{outbox_id}",
            },
        )
    except Exception as exc:
        # Never persist response bodies or credentials in operational logs.
        try:
            await _mark_failed(pool, row, type(exc).__name__)
        except Exception:
            logger.exception("Could not persist retry state for outbox event %s", outbox_id)
        return False

    if not 200 <= response.status_code < 300:
        try:
            await _mark_failed(pool, row, f"http_status_{response.status_code}")
        except Exception:
            logger.exception("Could not persist HTTP-failure retry state for outbox event %s", outbox_id)
        return False

    try:
        marked = await _mark_processed(pool, row)
    except Exception:
        # The receiver may already have accepted the event. The lease will expire
        # and the same Idempotency-Key will be reused on retry.
        logger.exception("Sink accepted outbox event %s but PostgreSQL acknowledgement failed", outbox_id)
        return False
    if not marked:
        logger.info("Ignored stale acknowledgement for outbox event %s", outbox_id)
        return False
    logger.info("Outbox event %s acknowledged by configured sink", outbox_id)
    return True


async def run_worker() -> None:
    database_url = _required_env("DATABASE_URL")
    sink_url = _validate_sink_url(_required_env("FULFILLMENT_SINK_URL"))
    sink_token = _required_env("FULFILLMENT_SINK_TOKEN")
    if len(sink_token) < 32:
        raise RuntimeError("FULFILLMENT_SINK_TOKEN must be at least 32 characters")

    poll_seconds = float(os.getenv("OUTBOX_POLL_SECONDS", str(DEFAULT_POLL_SECONDS)))
    batch_size = int(os.getenv("OUTBOX_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
    if not 0.25 <= poll_seconds <= 60:
        raise RuntimeError("OUTBOX_POLL_SECONDS must be between 0.25 and 60")
    if not 1 <= batch_size <= 20:
        raise RuntimeError("OUTBOX_BATCH_SIZE must be between 1 and 20")

    pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=3,
        command_timeout=30,
    )
    try:
        async with pool.acquire() as conn:
            schema_ready = await conn.fetchval(
                """
                SELECT to_regclass('public.garcar_v6_outbox') IS NOT NULL
                  AND to_regclass('public.garcar_v6_exceptions') IS NOT NULL
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
                """
            )
        if not schema_ready:
            raise RuntimeError("Garcar v6 outbox schema is not installed")

        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            logger.info("Outbox relay started; polling every %s seconds", poll_seconds)
            while True:
                rows = await _claim_batch(pool, batch_size, LEASE_SECONDS)
                if not rows:
                    await asyncio.sleep(poll_seconds)
                    continue
                # Dispatch a bounded batch concurrently so later rows do not lose
                # their lease while earlier requests are waiting on the network.
                await asyncio.gather(
                    *(_dispatch_one(pool, client, sink_url, sink_token, row) for row in rows)
                )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_worker())
