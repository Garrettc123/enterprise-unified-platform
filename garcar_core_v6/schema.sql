-- Garcar Enterprise v6.0 isolated core schema.
-- All tables are prefixed to avoid collisions with the existing platform schema.
-- Apply only to a dedicated database after reviewing backup and migration policy.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN
  CREATE TYPE garcar_v6_process_stage AS ENUM (
    'prospect_identified', 'enrichment_completed', 'proposal_dispatched',
    'payment_settled', 'fulfillment_queued', 'fulfillment_in_progress', 'qa_passed',
    'delivered_and_accepted', 'reconciled', 'exception_halted'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Upgrade a previously initialized v6 database without replacing existing tables.
ALTER TYPE garcar_v6_process_stage
  ADD VALUE IF NOT EXISTS 'fulfillment_queued' AFTER 'payment_settled';

DO $$ BEGIN
  CREATE TYPE garcar_v6_exception_severity AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS garcar_v6_organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS garcar_v6_customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID REFERENCES garcar_v6_organizations(id) ON DELETE CASCADE,
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255),
  is_suppressed BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS garcar_v6_offers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  version INT NOT NULL DEFAULT 1,
  fixed_price_cents BIGINT NOT NULL CHECK (fixed_price_cents >= 0),
  delivery_template_id VARCHAR(100) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS garcar_v6_opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL REFERENCES garcar_v6_customers(id) ON DELETE CASCADE,
  offer_id UUID REFERENCES garcar_v6_offers(id),
  stage garcar_v6_process_stage NOT NULL DEFAULT 'prospect_identified',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS garcar_v6_agreements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL REFERENCES garcar_v6_opportunities(id) ON DELETE CASCADE,
  terms_hash VARCHAR(64) NOT NULL,
  agreed_price_cents BIGINT CHECK (agreed_price_cents >= 0),
  offer_version INT CHECK (offer_version >= 1),
  signed_at TIMESTAMPTZ,
  checkout_url TEXT
);

-- Older v6 agreement rows remain NULL until explicitly reviewed/re-recorded.
-- The webhook handler fails closed for signed agreements without locked price/version.
ALTER TABLE garcar_v6_agreements
  ADD COLUMN IF NOT EXISTS agreed_price_cents BIGINT CHECK (agreed_price_cents >= 0);
ALTER TABLE garcar_v6_agreements
  ADD COLUMN IF NOT EXISTS offer_version INT CHECK (offer_version >= 1);

CREATE TABLE IF NOT EXISTS garcar_v6_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id UUID NOT NULL REFERENCES garcar_v6_agreements(id),
  customer_id UUID NOT NULL REFERENCES garcar_v6_customers(id),
  amount_cents BIGINT NOT NULL CHECK (amount_cents >= 0),
  stage garcar_v6_process_stage NOT NULL DEFAULT 'payment_settled',
  stripe_payment_intent_id VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- One signed agreement can settle into at most one order, even under concurrent events.
CREATE UNIQUE INDEX IF NOT EXISTS idx_garcar_v6_orders_agreement_unique
  ON garcar_v6_orders(agreement_id);

CREATE TABLE IF NOT EXISTS garcar_v6_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES garcar_v6_orders(id),
  stripe_payment_intent_id VARCHAR(255) UNIQUE NOT NULL,
  amount_received_cents BIGINT NOT NULL CHECK (amount_received_cents >= 0),
  currency VARCHAR(10) NOT NULL,
  status VARCHAR(50) NOT NULL,
  stripe_event_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS garcar_v6_payouts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stripe_payout_id VARCHAR(255) UNIQUE NOT NULL,
  amount_cents BIGINT NOT NULL,
  arrival_date DATE NOT NULL,
  is_reconciled BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS garcar_v6_bank_matches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payout_id UUID NOT NULL REFERENCES garcar_v6_payouts(id) ON DELETE CASCADE,
  bank_transaction_id VARCHAR(255) UNIQUE NOT NULL,
  matched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS garcar_v6_delivery_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL UNIQUE REFERENCES garcar_v6_orders(id) ON DELETE CASCADE,
  stage garcar_v6_process_stage NOT NULL DEFAULT 'fulfillment_in_progress',
  prerequisites_met BOOLEAN NOT NULL DEFAULT FALSE,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS garcar_v6_artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  delivery_job_id UUID NOT NULL REFERENCES garcar_v6_delivery_jobs(id) ON DELETE CASCADE,
  storage_path TEXT NOT NULL,
  sha256 VARCHAR(64),
  qa_status VARCHAR(50) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS garcar_v6_exceptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  related_entity_id UUID NOT NULL,
  severity garcar_v6_exception_severity NOT NULL DEFAULT 'medium',
  module_source VARCHAR(100) NOT NULL,
  error_message TEXT NOT NULL,
  resolved BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Stripe's event ID is the primary idempotency key. Event receipt and financial
-- writes occur in the same transaction, so a failed transaction can safely retry.
CREATE TABLE IF NOT EXISTS garcar_v6_stripe_events (
  stripe_event_id VARCHAR(255) PRIMARY KEY,
  event_type VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL CHECK (status IN ('processed', 'ignored', 'held_for_review')),
  received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Upgrade existing v6 schemas to preserve review state and trace exceptions to Stripe events.
ALTER TABLE garcar_v6_stripe_events
  DROP CONSTRAINT IF EXISTS garcar_v6_stripe_events_status_check;
ALTER TABLE garcar_v6_stripe_events
  ADD CONSTRAINT garcar_v6_stripe_events_status_check
  CHECK (status IN ('processed', 'ignored', 'held_for_review'));
ALTER TABLE garcar_v6_exceptions
  ADD COLUMN IF NOT EXISTS stripe_event_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_garcar_v6_exceptions_stripe_event
  ON garcar_v6_exceptions(stripe_event_id);

-- Transactional outbox makes fulfillment scheduling durable across process restarts.
CREATE TABLE IF NOT EXISTS garcar_v6_outbox (
  id BIGSERIAL PRIMARY KEY,
  event_type VARCHAR(100) NOT NULL,
  aggregate_id UUID NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  available_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  attempts INT NOT NULL DEFAULT 0,
  locked_at TIMESTAMPTZ,
  lease_token UUID,
  processed_at TIMESTAMPTZ,
  dead_lettered_at TIMESTAMPTZ,
  last_error TEXT
);

-- CREATE TABLE IF NOT EXISTS does not add columns to an existing table.
ALTER TABLE garcar_v6_outbox ADD COLUMN IF NOT EXISTS lease_token UUID;
ALTER TABLE garcar_v6_outbox ADD COLUMN IF NOT EXISTS dead_lettered_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_garcar_v6_opportunities_stage ON garcar_v6_opportunities(stage);
CREATE INDEX IF NOT EXISTS idx_garcar_v6_delivery_jobs_stage ON garcar_v6_delivery_jobs(stage);
CREATE INDEX IF NOT EXISTS idx_garcar_v6_exceptions_open ON garcar_v6_exceptions(resolved, severity);
-- Rebuild the pending index so upgraded databases also exclude dead-lettered rows.
DROP INDEX IF EXISTS idx_garcar_v6_outbox_pending;
CREATE INDEX idx_garcar_v6_outbox_pending ON garcar_v6_outbox(available_at, id)
  WHERE processed_at IS NULL AND dead_lettered_at IS NULL;
