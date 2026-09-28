import { afterEach, describe, expect, it, vi } from "vitest";
import { verifySignature } from "../src/dodo";
import { handle, sha256Hex, type Env, type KeyChange, type License, type Store } from "../src/relay";

const SECRET_LENGTH = 24;
const randomBytes = (length: number) => crypto.getRandomValues(new Uint8Array(length));
const base64 = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes));
const SECRET_BYTES = randomBytes(SECRET_LENGTH);
const SECRET = `whsec_${base64(SECRET_BYTES)}`;
const ENV: Env = {
  OPENAI_API_KEY: "sk-real",
  AI_GATEWAY_API_KEY: "gw-real",
  RELAY_DATABASE_URL: "",
  OPENAI_BASE_URL: "https://openai.test/v1",
  AI_GATEWAY_BASE_URL: "https://gateway.test/v1",
  AWS_ACCESS_KEY_ID: "AKIDEXAMPLE",
  AWS_SECRET_ACCESS_KEY: "secret",
  POLLY_REGION: "ap-south-1",
  DODO_WEBHOOK_SECRET: SECRET,
  DODO_API_KEY: "dodo-api-key",
  DODO_API_BASE_URL: "https://dodo.test",
};
const MAC_APP_KEY_SHAPE = /^zoya_[A-Za-z0-9_-]{20,200}$/;
const GRANT_ID = "entg_w0ZCJZgNXuNDdMVzvja6p";

type Row = { active: boolean; at: string; grantId: string };

function fakeStore() {
  const rows = new Map<string, Row>();
  const events = new Set<string>();
  const changes: KeyChange[] = [];
  const store: Store = {
    async find(hash) {
      const row = rows.get(hash);
      const license: License = { id: 1, active: row?.active ?? false, capCents: 800, spentCents: 0 };
      return row ? license : null;
    },
    async record() {},
    async seen(webhookId) {
      return events.has(webhookId);
    },
    async recordEvent(webhookId, _type, change) {
      events.add(webhookId);
      if (!change) return;
      changes.push(change);
      if (change.keyHash) {
        rows.set(change.keyHash, { active: change.active, at: change.at, grantId: change.grantId });
        return;
      }
      for (const row of rows.values()) if (row.grantId === change.grantId) Object.assign(row, { active: change.active, at: change.at });
    },
  };
  return { store, rows, events, changes };
}

function grantEvent(type: string, grant: Record<string, unknown>, timestamp = "2026-10-01T10:00:00.000000Z") {
  return {
    business_id: "bus_H4ekzPSlcg",
    type,
    timestamp,
    data: {
      payload_type: "EntitlementGrant",
      id: GRANT_ID,
      customer_id: "cus_abc123",
      subscription_id: "sub_pro_monthly_001",
      integration_type: "license_key",
      status: "Pending",
      license_key: null,
      ...grant,
    },
  };
}

async function hmac(secret: Uint8Array, content: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", secret, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return base64(new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(content))));
}

async function signedRequest(event: unknown, id = "msg_1", secret = SECRET_BYTES, seconds = Math.floor(Date.now() / 1000)) {
  const body = JSON.stringify(event);
  const signature = await hmac(secret, `${id}.${seconds}.${body}`);
  return new Request("https://relay.test/webhooks/dodo", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "webhook-id": id,
      "webhook-timestamp": String(seconds),
      "webhook-signature": `v1,${signature}`,
    },
    body,
  });
}

function dodoApi(status = 200) {
  const issued: { url: string; auth: string; key: string }[] = [];
  const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    const headers = init.headers as Record<string, string>;
    issued.push({ url, auth: headers.Authorization, key: JSON.parse(String(init.body)).key });
    return Response.json({ id: GRANT_ID, status: "Delivered" }, { status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { issued, fetchMock };
}

async function send(store: Store, request: Request) {
  return handle(request, ENV, store, () => {});
}

async function licenseStatus(store: Store, key: string) {
  const request = new Request("https://relay.test/v1/license", { headers: { Authorization: `Bearer ${key}` } });
  return (await send(store, request)).status;
}

async function activate(store: Store) {
  const { issued } = dodoApi();
  await send(store, await signedRequest(grantEvent("entitlement_grant.created", {}), "msg_created"));
  return issued[0].key;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("Dodo webhook signature", () => {
  it("accepts the Standard Webhooks reference vector", async () => {
    const signed = {
      id: "msg_p5jXN8AQM9LWM0D4loKWxJek",
      timestamp: "1614265330",
      signatures: "v1,bm9wZQ== v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE=",
      body: '{"test": 2432232314}',
    };
    expect(await verifySignature("whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw", signed, 1614265330)).toBe(true);
  });

  it("rejects a body signed with the wrong secret", async () => {
    const { store, events } = fakeStore();
    const { fetchMock } = dodoApi();
    const request = await signedRequest(grantEvent("entitlement_grant.created", {}), "msg_1", randomBytes(SECRET_LENGTH));
    const response = await send(store, request);
    expect(response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(events.size).toBe(0);
  });

  it("rejects a tampered body", async () => {
    const { store } = fakeStore();
    dodoApi();
    const signed = await signedRequest(grantEvent("entitlement_grant.created", {}));
    const tampered = new Request(signed.url, { method: "POST", headers: signed.headers, body: (await signed.text()) + " " });
    expect((await send(store, tampered)).status).toBe(401);
  });

  it("rejects a replay older than five minutes", async () => {
    const { store } = fakeStore();
    dodoApi();
    const old = Math.floor(Date.now() / 1000) - 6 * 60;
    const response = await send(store, await signedRequest(grantEvent("entitlement_grant.created", {}), "msg_1", SECRET_BYTES, old));
    expect(response.status).toBe(401);
  });

  it("rejects a timestamp more than five minutes in the future", async () => {
    const { store } = fakeStore();
    dodoApi();
    const future = Math.floor(Date.now() / 1000) + 6 * 60;
    const response = await send(store, await signedRequest(grantEvent("entitlement_grant.created", {}), "msg_1", SECRET_BYTES, future));
    expect(response.status).toBe(401);
  });

  it("rejects a request with no signature", async () => {
    const { store } = fakeStore();
    const request = new Request("https://relay.test/webhooks/dodo", { method: "POST", body: "{}" });
    expect((await send(store, request)).status).toBe(401);
  });
});

describe("Dodo subscription lifecycle", () => {
  it("activation issues a Zoya key through Dodo and the key works", async () => {
    const { store, rows } = fakeStore();
    const key = await activate(store);
    expect(key).toMatch(MAC_APP_KEY_SHAPE);
    expect(rows.get(await sha256Hex(key))?.active).toBe(true);
    expect(await licenseStatus(store, key)).toBe(200);
  });

  it("fulfils the pending grant at Dodo's documented endpoint with the API key", async () => {
    const { store } = fakeStore();
    const { issued } = dodoApi();
    await send(store, await signedRequest(grantEvent("entitlement_grant.created", {})));
    expect(issued).toHaveLength(1);
    expect(issued[0].url).toBe(`https://dodo.test/grants/${GRANT_ID}/license-key`);
    expect(issued[0].auth).toBe("Bearer dodo-api-key");
  });

  it("the same event delivered twice changes nothing", async () => {
    const { store, changes } = fakeStore();
    const { fetchMock } = dodoApi();
    const event = grantEvent("entitlement_grant.created", {});
    const first = await send(store, await signedRequest(event, "msg_same"));
    const second = await send(store, await signedRequest(event, "msg_same"));
    expect([first.status, second.status]).toEqual([200, 200]);
    expect(await second.json()).toEqual({ received: true, duplicate: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(changes).toHaveLength(1);
  });

  it("cancellation deactivates the key", async () => {
    const { store } = fakeStore();
    const key = await activate(store);
    const revoked = grantEvent(
      "entitlement_grant.revoked",
      { status: "Revoked", revocation_reason: "subscription_cancelled", license_key: { key, status: "disabled" } },
      "2026-11-01T10:00:00.000000Z",
    );
    expect((await send(store, await signedRequest(revoked, "msg_revoked"))).status).toBe(200);
    expect(await licenseStatus(store, key)).toBe(401);
  });

  it("a restored grant after a failed payment reactivates the key", async () => {
    const { store } = fakeStore();
    const key = await activate(store);
    const onHold = grantEvent("entitlement_grant.revoked", { status: "Revoked", license_key: { key } }, "2026-11-01T10:00:00Z");
    const restored = grantEvent("entitlement_grant.delivered", { status: "Delivered", license_key: { key } }, "2026-11-03T10:00:00Z");
    await send(store, await signedRequest(onHold, "msg_hold"));
    expect(await licenseStatus(store, key)).toBe(401);
    await send(store, await signedRequest(restored, "msg_restored"));
    expect(await licenseStatus(store, key)).toBe(200);
  });

  it("a grant Dodo already fulfilled is acknowledged without a new key", async () => {
    const { store, events, changes } = fakeStore();
    dodoApi(409);
    const response = await send(store, await signedRequest(grantEvent("entitlement_grant.created", {}), "msg_retry"));
    expect(response.status).toBe(200);
    expect(changes).toHaveLength(0);
    expect(events.has("msg_retry")).toBe(true);
  });

  it("a failed fulfilment is not recorded, so Dodo's retry runs it again", async () => {
    const { store, events } = fakeStore();
    dodoApi(500);
    const response = await send(store, await signedRequest(grantEvent("entitlement_grant.created", {}), "msg_fail"));
    expect(response.status).toBe(503);
    expect(events.has("msg_fail")).toBe(false);
  });

  it("ignores events that are not license-key grants", async () => {
    const { store, changes } = fakeStore();
    const { fetchMock } = dodoApi();
    const discord = grantEvent("entitlement_grant.created", { integration_type: "discord" });
    const subscription = { type: "subscription.active", timestamp: "2026-10-01T10:00:00Z", data: { payload_type: "Subscription" } };
    expect((await send(store, await signedRequest(discord, "msg_a"))).status).toBe(200);
    expect((await send(store, await signedRequest(subscription, "msg_b"))).status).toBe(200);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(changes).toHaveLength(0);
  });

  it("a revoke whose payload carries no key still deactivates the grant's key", async () => {
    const { store } = fakeStore();
    const key = await activate(store);
    const revoked = grantEvent("entitlement_grant.revoked", { status: "Revoked", license_key: null }, "2026-11-01T10:00:00Z");
    expect((await send(store, await signedRequest(revoked, "msg_revoked"))).status).toBe(200);
    expect(await licenseStatus(store, key)).toBe(401);
  });

  it("a restore whose payload carries no key still reactivates the grant's key", async () => {
    const { store } = fakeStore();
    const key = await activate(store);
    const onHold = grantEvent("entitlement_grant.revoked", { status: "Revoked", license_key: null }, "2026-11-01T10:00:00Z");
    const restored = grantEvent("entitlement_grant.delivered", { status: "Delivered", license_key: null }, "2026-11-03T10:00:00Z");
    await send(store, await signedRequest(onHold, "msg_hold"));
    await send(store, await signedRequest(restored, "msg_restored"));
    expect(await licenseStatus(store, key)).toBe(200);
  });

  it("a fulfilment call that hangs is abandoned with 503 and not recorded", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const { store, events } = fakeStore();
    const fetchMock = vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => init.signal?.addEventListener("abort", () => reject(new Error("aborted")))),
    );
    vi.stubGlobal("fetch", fetchMock);
    const pending = send(store, await signedRequest(grantEvent("entitlement_grant.created", {}), "msg_hang"));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await vi.advanceTimersByTimeAsync(30_000);
    expect((await pending).status).toBe(503);
    expect(events.has("msg_hang")).toBe(false);
  });

  it("concurrent deliveries of one created event store exactly one working key", async () => {
    const { store, changes } = fakeStore();
    const accepted: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init: RequestInit) => {
        if (accepted.length) return new Response(null, { status: 409 });
        accepted.push(JSON.parse(String(init.body)).key);
        return Response.json({ status: "Delivered" });
      }),
    );
    const event = grantEvent("entitlement_grant.created", {});
    const responses = await Promise.all([send(store, await signedRequest(event, "msg_c")), send(store, await signedRequest(event, "msg_c"))]);
    expect(responses.map((r) => r.status)).toEqual([200, 200]);
    expect(changes).toHaveLength(1);
    expect(await licenseStatus(store, accepted[0])).toBe(200);
  });

  it("a key Dodo accepted but the database missed starts working when Dodo's delivered event arrives", async () => {
    const { store } = fakeStore();
    const { issued } = dodoApi();
    const recordEvent = store.recordEvent;
    store.recordEvent = async () => {
      throw new Error("neon down");
    };
    const created = grantEvent("entitlement_grant.created", {});
    expect((await send(store, await signedRequest(created, "msg_created"))).status).toBe(503);
    store.recordEvent = recordEvent;
    dodoApi(409);
    expect((await send(store, await signedRequest(created, "msg_created"))).status).toBe(200);
    const key = issued[0].key;
    expect(await licenseStatus(store, key)).toBe(401);
    const delivered = grantEvent("entitlement_grant.delivered", { status: "Delivered", license_key: { key } }, "2026-10-01T10:00:05Z");
    expect((await send(store, await signedRequest(delivered, "msg_delivered"))).status).toBe(200);
    expect(await licenseStatus(store, key)).toBe(200);
  });

  it("never logs a license key or a Dodo secret", async () => {
    const logs = vi.spyOn(console, "log").mockImplementation(() => {});
    const { store } = fakeStore();
    const key = await activate(store);
    const revoked = grantEvent("entitlement_grant.revoked", { status: "Revoked", license_key: { key } }, "2026-11-01T10:00:00Z");
    await send(store, await signedRequest(revoked, "msg_revoked"));
    dodoApi(500);
    await send(store, await signedRequest(grantEvent("entitlement_grant.created", {}), "msg_fail"));
    const output = logs.mock.calls.flat().join("\n");
    expect(output).toContain("dodo_applied");
    for (const secret of [key, SECRET, base64(SECRET_BYTES), ENV.DODO_API_KEY]) expect(output).not.toContain(secret);
  });
});
