import test from "node:test";
import assert from "node:assert/strict";
import handler from "../api/v1/orchestration/status.js";

function response() {
  return {
    code: null,
    headers: {},
    jsonBody: null,
    setHeader(key, val) { this.headers[key.toLowerCase()] = val; return this; },
    status(code) { this.code = code; return this; },
    json(body) { this.jsonBody = body; return this; },
  };
}
function upstream(url) {
  const host = new URL(url).hostname;
  if (host.startsWith("mars-api-")) return { status: "ok", service: "mars-api" };
  if (host.startsWith("mars-production-")) return { status: "healthy", service: "MARS" };
  if (host.startsWith("rhns-governed-worker-")) return { alive: true };
  if (host.startsWith("garcar-rhns-core-")) return { status: "live", service: "garcar-rhns-core" };
  throw new Error("unknown destination");
}
const mockJson = (data, status=200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });

test("reports four live services without claiming full autonomy", async () => {
  const saved = globalThis.fetch, calls = [];
  globalThis.fetch = async (url, opts) => {
    calls.push({url, opts});
    return mockJson(upstream(url));
  };
  try {
    const res = response();
    await handler({ method: "GET" }, res);
    assert.equal(res.code, 200);
    assert.equal(res.jsonBody.status, "bounded_core_online");
    assert.equal(res.jsonBody.read_only, true);
    assert.equal(res.jsonBody.full_autonomous_sync_enabled, false);
    assert.equal(res.jsonBody.full_platform_certified, false);
    assert.equal(res.jsonBody.external_actions_enabled, false);
    assert.equal(res.jsonBody.components.rhns_worker.state, "online");
    assert.match(res.headers["cache-control"], /s-maxage=60/);
    assert.equal(calls.length, 4);
    assert.ok(calls.every(c => c.opts.method === "GET" && c.opts.redirect === "error"));
  } finally {
    globalThis.fetch = saved;
  }
});

test("fails closed when a 200 response is actually HTML", async () => {
  const saved = globalThis.fetch;
  globalThis.fetch = async (url) => url.includes("mars-api-")
    ? new Response("<!doctype html>", {status: 200, headers: {"content-type":"text/html"}})
    : mockJson(upstream(url));
  try {
    const res = response();
    await handler({method: "GET"}, res);
    assert.equal(res.code, 503);
    assert.equal(res.jsonBody.status, "degraded");
    assert.equal(res.jsonBody.components.mars_api.state, "unverified");
    assert.equal(res.jsonBody.full_autonomous_sync_enabled, false);
  } finally { globalThis.fetch = saved; }
});

test("rejects non-GET without contacting any upstream", async () => {
  const saved = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("unexpected call"); };
  try {
    const res = response();
    await handler({method: "POST"}, res);
    assert.equal(res.code, 405);
    assert.equal(res.headers.allow, "GET");
  } finally { globalThis.fetch = saved; }
});

test("fails closed on inaccessible upstream", async () => {
  const saved = globalThis.fetch;
  globalThis.fetch = async (url) => url.includes("rhns-governed-worker-")
    ? Promise.reject(new Error("network failure"))
    : mockJson(upstream(url));
  try {
    const res = response();
    await handler({method: "GET"}, res);
    assert.equal(res.code, 503);
    assert.equal(res.jsonBody.components.rhns_worker.state, "unreachable");
  } finally { globalThis.fetch = saved; }
});
