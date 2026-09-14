// ponytail: best-effort, in memory per server instance. Serverless instances don't share it and it
// resets on cold start. Upgrade path: a shared store (Upstash Redis / Vercel KV) keyed the same way.

const WINDOW_MS = 10 * 60 * 1000;
const MAX_TRACKED_KEYS = 10_000;
const hits = new Map<string, number[]>();

export function isRateLimited(key: string, limit: number, now = Date.now()): boolean {
  if (hits.size > MAX_TRACKED_KEYS) hits.clear();
  const recent = (hits.get(key) ?? []).filter((time) => now - time < WINDOW_MS);
  const limited = recent.length >= limit;
  hits.set(key, limited ? recent : [...recent, now]);
  return limited;
}

export function clientIp(request: Request): string {
  return request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
}
