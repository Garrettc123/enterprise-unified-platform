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

test('authenticated dashboard never defaults to an arbitrary organization', () => {
  const dashboard = readFileSync(new URL('../src/pages/Dashboard.tsx', import.meta.url), 'utf8');
  assert.equal(dashboard.includes('useState(1) // Default org ID'), false);
  assert.match(dashboard, /organizationsApi\.list/);
  assert.match(dashboard, /setOrganizationId/);
});

test('analytics and organization endpoints check tenant membership', () => {
  const analytics = readFileSync(new URL('../../backend/routers/analytics.py', import.meta.url), 'utf8');
  const orgs = readFileSync(new URL('../../backend/routers/organizations.py', import.meta.url), 'utf8');
  assert.match(analytics, /require_organization_access/);
  assert.match(analytics, /Organization membership required/);
  assert.match(orgs, /require_membership/);
  assert.match(orgs, /Organization access denied/);
  assert.match(orgs, /manage=True/);
});
