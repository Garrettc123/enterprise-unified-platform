#!/usr/bin/env bash
set -Eeuo pipefail

# Isolated, local-by-default deployment. No fallback credentials and no reload mode.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="$ROOT_DIR/garcar_core_v6"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  printf 'Required command missing: %s\n' "$PYTHON_BIN" >&2
  exit 1
}

: "${DATABASE_URL:?Set DATABASE_URL in your protected environment}"
: "${STRIPE_WEBHOOK_SECRET:?Set STRIPE_WEBHOOK_SECRET in your protected environment}"
: "${STRIPE_EXPECT_LIVE:?Set STRIPE_EXPECT_LIVE to true or false}"
case "$STRIPE_EXPECT_LIVE" in
  true|false) ;;
  *)
    echo "STRIPE_EXPECT_LIVE must be exactly true or false." >&2
    exit 1
    ;;
esac
if [[ "$STRIPE_WEBHOOK_SECRET" != whsec_* ]]; then
  echo "STRIPE_WEBHOOK_SECRET does not look like a Stripe webhook secret." >&2
  exit 1
fi

# Require explicit operator opt-in before applying DDL to the configured database.
if [[ "${GARCAR_ALLOW_SCHEMA_APPLY:-false}" != "true" ]]; then
  echo "Refusing to apply schema: confirm a dedicated non-production database and set GARCAR_ALLOW_SCHEMA_APPLY=true." >&2
  exit 1
fi

if [[ ! -d "$CORE_DIR/.venv" ]]; then
  "$PYTHON_BIN" -m venv "$CORE_DIR/.venv"
fi
"$CORE_DIR/.venv/bin/python" -m pip install --disable-pip-version-check -r "$CORE_DIR/requirements.txt"

echo "Applying isolated Garcar v6 schema..."
# Use the same asyncpg driver as the service. The database URI is read from the
# process environment, never passed as a command-line argument.
GARCAR_SCHEMA_FILE="$CORE_DIR/schema.sql" "$CORE_DIR/.venv/bin/python" - <<'PY'
import asyncio
import os
from pathlib import Path

import asyncpg

async def main():
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise SystemExit(
            "DATABASE_URL must use postgresql:// or postgres:// "
            "(not postgresql+asyncpg://)."
        )
    schema_path = Path(os.environ["GARCAR_SCHEMA_FILE"])
    conn = await asyncpg.connect(dsn=database_url, timeout=20)
    try:
        await conn.execute(schema_path.read_text(encoding="utf-8"))
    finally:
        await conn.close()

asyncio.run(main())
PY

echo "Starting Garcar v6 on $HOST:$PORT (local by default)."
exec "$CORE_DIR/.venv/bin/uvicorn" main:app --app-dir "$CORE_DIR" --host "$HOST" --port "$PORT"
