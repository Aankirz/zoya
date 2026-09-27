import { fail, sha256Hex, type Env, type KeyChange, type Store } from "./relay";

export const DODO_WEBHOOK_PATH = "/webhooks/dodo";
const TIMESTAMP_TOLERANCE_SECONDS = 5 * 60;
const SECRET_PREFIX = "whsec_";
const SIGNATURE_PREFIX = "v1,";
const KEY_PREFIX = "zoya_";
const KEY_BYTES = 32;
const LICENSE_KEY_GRANT = "license_key";
const PENDING = "Pending";
const GRANT_CREATED = "entitlement_grant.created";
const GRANT_DELIVERED = "entitlement_grant.delivered";
const GRANT_REVOKED = "entitlement_grant.revoked";
const ALREADY_FULFILLED = 409;

type Grant = {
  id: string;
  customer_id: string;
  status: string;
  integration_type: string;
  license_key: { key?: unknown } | null;
};
type DodoEvent = { type: string; timestamp: string; data: Grant };
type Signed = { id: string; timestamp: string; signatures: string; body: string };

export class FulfilmentError extends Error {
  constructor(readonly status: number) {
    super(`Dodo refused the license key with status ${status}`);
    this.name = "FulfilmentError";
  }
}

function bytesFromBase64(text: string): Uint8Array | null {
  try {
    return Uint8Array.from(atob(text), (char) => char.charCodeAt(0));
  } catch {
    return null;
  }
}

function freshTimestamp(timestamp: string, nowSeconds: number): boolean {
  if (!/^\d+$/.test(timestamp)) return false;
  return Math.abs(nowSeconds - Number(timestamp)) <= TIMESTAMP_TOLERANCE_SECONDS;
}

export async function verifySignature(secret: string, signed: Signed, nowSeconds: number): Promise<boolean> {
  if (!secret || !signed.id || !signed.signatures || !freshTimestamp(signed.timestamp, nowSeconds)) return false;
  const secretBytes = bytesFromBase64(secret.startsWith(SECRET_PREFIX) ? secret.slice(SECRET_PREFIX.length) : secret);
  if (!secretBytes?.length) return false;
  const key = await crypto.subtle.importKey("raw", secretBytes, { name: "HMAC", hash: "SHA-256" }, false, ["verify"]);
  const content = new TextEncoder().encode(`${signed.id}.${signed.timestamp}.${signed.body}`);
  for (const candidate of signed.signatures.split(" ")) {
    if (!candidate.startsWith(SIGNATURE_PREFIX)) continue;
    const signature = bytesFromBase64(candidate.slice(SIGNATURE_PREFIX.length));
    if (signature && (await crypto.subtle.verify("HMAC", key, signature, content))) return true;
  }
  return false;
}

function parseEvent(body: string): DodoEvent | null {
  try {
    const event = JSON.parse(body);
    const valid = typeof event?.type === "string" && typeof event?.timestamp === "string" && event?.data;
    return valid ? (event as DodoEvent) : null;
  } catch {
    return null;
  }
}

export function newLicenseKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(KEY_BYTES));
  const base64 = btoa(String.fromCharCode(...bytes));
  return KEY_PREFIX + base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function fulfil(env: Env, grantId: string): Promise<string | null> {
  const key = newLicenseKey();
  const base = env.DODO_API_BASE_URL.replace(/\/$/, "");
  const response = await fetch(`${base}/grants/${encodeURIComponent(grantId)}/license-key`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.DODO_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
  if (response.status === ALREADY_FULFILLED) return null;
  if (!response.ok) throw new FulfilmentError(response.status);
  return key;
}

function deliveredKey(grant: Grant): string | null {
  const key = grant.license_key?.key;
  return typeof key === "string" && key ? key : null;
}

async function keyAndState(event: DodoEvent, env: Env): Promise<{ key: string; active: boolean } | null> {
  const grant = event.data;
  if (grant.integration_type !== LICENSE_KEY_GRANT) return null;
  const key = deliveredKey(grant);
  if (event.type === GRANT_REVOKED) return key ? { key, active: false } : null;
  if (event.type !== GRANT_CREATED && event.type !== GRANT_DELIVERED) return null;
  if (key) return { key, active: true };
  if (event.type !== GRANT_CREATED || grant.status !== PENDING) return null;
  const issued = await fulfil(env, grant.id);
  return issued ? { key: issued, active: true } : null;
}

export async function changeFor(event: DodoEvent, env: Env): Promise<KeyChange | null> {
  const found = await keyAndState(event, env);
  if (!found) return null;
  return {
    keyHash: await sha256Hex(found.key),
    grantId: event.data.id,
    customerId: event.data.customer_id,
    active: found.active,
    at: event.timestamp,
  };
}

export async function handleDodo(request: Request, env: Env, store: Store): Promise<Response> {
  const headers = request.headers;
  const signed: Signed = {
    id: headers.get("webhook-id") ?? "",
    timestamp: headers.get("webhook-timestamp") ?? "",
    signatures: headers.get("webhook-signature") ?? "",
    body: await request.text(),
  };
  if (!(await verifySignature(env.DODO_WEBHOOK_SECRET, signed, Math.floor(Date.now() / 1000)))) {
    log({ event: "dodo_signature_invalid", status: 401 });
    return fail(401, "dodo_signature_invalid", "The webhook signature is not valid.");
  }
  const event = parseEvent(signed.body);
  if (!event) return fail(400, "invalid_json", "The webhook body is not a Dodo event.");
  return apply(signed.id, event, env, store);
}

async function apply(webhookId: string, event: DodoEvent, env: Env, store: Store): Promise<Response> {
  try {
    if (await store.seen(webhookId)) {
      log({ event: "dodo_duplicate", type: event.type, status: 200 });
      return Response.json({ received: true, duplicate: true });
    }
    const change = await changeFor(event, env);
    await store.recordEvent(webhookId, event.type, change);
    log({ event: "dodo_applied", type: event.type, active: change?.active ?? null, status: 200 });
    return Response.json({ received: true });
  } catch (error) {
    const status = error instanceof FulfilmentError ? error.status : null;
    log({ event: "dodo_failed", type: event.type, upstream: status, error: error instanceof Error ? error.name : typeof error });
    return fail(503, "dodo_not_applied", "The event could not be applied; Dodo will retry.");
  }
}

function log(entry: Record<string, unknown>): void {
  console.log(JSON.stringify(entry));
}
