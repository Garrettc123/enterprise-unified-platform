/**
 * Read-only UEEP/RHNS observability endpoint.
 *
 * This is NOT the autonomous sync engine. It never runs customer actions,
 * queries private services, pays a provider, or asserts QIH readiness.
 * All upstream hosts are fixed, existing public health endpoints.
 */
const DEPENDENCIES = Object.freeze({
  mars_api: {
    url: "https://mars-api-carrolgarrett5-5537s-projects.vercel.app/health",
    healthy: (body) => body?.service === "mars-api" && body?.status === "ok",
  },
  mars_reasoning: {
    url: "https://mars-production-carrolgarrett5-5537s-projects.vercel.app/health",
    healthy: (body) => body?.service === "MARS" && body?.status === "healthy",
  },
  rhns_worker: {
    url: "https://rhns-governed-worker-production.up.railway.app/health",
    healthy: (body) => body?.alive === true,
  },
  rhns_cognitive: {
    url: "https://garcar-rhns-core-7r0pm1csc-carrolgarrett5-5537s-projects.vercel.app/health",
    healthy: (body) => body?.service === "garcar-rhns-core" && body?.status === "live",
  },
});

async function observe(name, spec) {
  try {
    const response = await fetch(spec.url, {
      method: "GET",
      redirect: "error",
      signal: AbortSignal.timeout(3000),
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    const mediaType = response.headers.get("content-type") ?? "";
    if (response.status !== 200 || !mediaType.includes("application/json")) {
      return [name, { state: "unverified", http_status: response.status }];
    }
    // Health-only fields; do not publish upstream key-availability metadata.
    const raw = await response.text();
    if (raw.length > 8192) return [name, { state: "unverified", reason: "oversized_health_response" }];
    const data = JSON.parse(raw);
    return [name, {
      state: spec.healthy(data) ? "online" : "unverified",
      http_status: response.status,
    }];
  } catch {
    return [name, { state: "unreachable" }];
  }
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "method_not_allowed" });
  }

  const pairs = await Promise.all(
    Object.entries(DEPENDENCIES).map(([name, spec]) => observe(name, spec)),
  );
  const services = Object.fromEntries(pairs);
  const operational = Object.values(services).every((x) => x.state === "online");
  res.setHeader("Cache-Control", "public, s-maxage=60, stale-while-revalidate=30");
  res.setHeader("X-Content-Type-Options", "nosniff");

  return res.status(operational ? 200 : 503).json({
    service: "ueep-governed-observability",
    status: operational ? "bounded_core_online" : "degraded",
    read_only: true,
    external_actions_enabled: false,
    full_autonomous_sync_enabled: false,
    full_platform_certified: false,
    components: services,
    unverified_modules: {
      ueep_ha_cluster: "no_verifiable_cluster_deployment",
      qih_telemetry: "supabase_project_access_not_verified",
    },
    checked_at: new Date().toISOString(),
  });
}
