import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const revenue = readFileSync(new URL('../../backend/routers/revenue.py', import.meta.url), 'utf8');

test('public homepage contains no synthetic revenue or live activity', () => {
  for (const pattern of ['Math.random()', '$104M+', '12847', '284650', "status: 'Live'", 'All Systems Operational']) {
    assert.equal(page.includes(pattern), false, pattern);
  }
  assert.match(page, /Not verified/);
});
test('unknown webhook signing secret must not permit unsigned events', () => {
  assert.match(revenue, /if not webhook_secret:/);
  assert.match(revenue, /Signed webhook processing is not configured/);
  assert.equal(revenue.includes('accept but log warning'), false);
});
test('volatile events are not marketed as reconciled MRR', () => {
  assert.match(revenue, /Durable Stripe reconciliation has not been implemented/);
  assert.match(revenue, /"verified_mrr": None/);
});
