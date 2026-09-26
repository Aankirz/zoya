import { afterEach, describe, expect, it, vi } from "vitest";
import { costCents, usageFrom } from "../src/cost";
import { handle, sha256Hex, type Env, type License, type Store } from "../src/relay";

const ENV: Env = {
  OPENAI_API_KEY: "sk-real",
  AI_GATEWAY_API_KEY: "gw-real",
  RELAY_DATABASE_URL: "",
  OPENAI_BASE_URL: "https://openai.test/v1",
  AI_GATEWAY_BASE_URL: "https://gateway.test/v1",
};
const GOOD = "zoya_good";
const REVOKED = "zoya_revoked";

type Recorded = { licenseId: number; cents: number };

async function fakeStore(licenses: Record<string, License>): Promise<Store & { recorded: Recorded[] }> {
  const byHash = new Map<string, License>();
  for (const [key, license] of Object.entries(licenses)) byHash.set(await sha256Hex(key), license);
  const recorded: Recorded[] = [];
  return {
    recorded,
    async find(hash) {
      return byHash.get(hash) ?? null;
    },
    async record(licenseId, _month, cents) {
      recorded.push({ licenseId, cents });
    },
  };
}

function license(overrides: Partial<License> = {}): License {
  return { id: 1, active: true, capCents: 800, spentCents: 0, ...overrides };
}

function upstream(reply: unknown, contentType = "application/json") {
  const sent: { url: string; body: Record<string, unknown>; auth: string }[] = [];
  const fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    const headers = init.headers as Record<string, string>;
    sent.push({ url, body: JSON.parse(String(init.body)), auth: headers.Authorization });
    const text = typeof reply === "string" ? reply : JSON.stringify(reply);
    return new Response(text, { status: 200, headers: { "Content-Type": contentType } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { sent, fetchMock };
}

async function call(store: Store, path: string, body: unknown, key = GOOD) {
  const waits: Promise<unknown>[] = [];
  const request = new Request(`https://relay.test${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const response = await handle(request, ENV, store, (p) => waits.push(p));
  const text = await response.text();
  await Promise.all(waits);
  return { status: response.status, text, json: () => JSON.parse(text) };
}

const CHAT_USAGE = {
  usage: {
    prompt_tokens: 1813,
    completion_tokens: 10,
    prompt_tokens_details: { cached_tokens: 3, cache_write_tokens: 1800 },
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("store is forced to false", () => {
  it.each(["/v1/chat/completions", "/v1/responses"])("on %s even when the client sent true", async (path) => {
    const store = await fakeStore({ [GOOD]: license() });
    const { sent } = upstream(CHAT_USAGE);
    await call(store, path, { model: "gpt-5.6-luna", store: true, input: "hi" });
    expect(sent[0].body.store).toBe(false);
    expect(sent[0].auth).toBe("Bearer sk-real");
  });

  it("asks a streamed chat completion for its usage", async () => {
    const store = await fakeStore({ [GOOD]: license() });
    const { sent } = upstream(CHAT_USAGE);
    await call(store, "/v1/chat/completions", {
      model: "gpt-5.6-luna",
      stream: true,
      stream_options: { include_usage: false },
    });
    expect(sent[0].body.stream_options).toEqual({ include_usage: true });
  });
});

describe("the monthly cap", () => {
  it("refuses a heavy call once this month's spend reaches the cap", async () => {
    const store = await fakeStore({ [GOOD]: license({ capCents: 1, spentCents: 1.2 }) });
    const { fetchMock } = upstream(CHAT_USAGE);
    const reply = await call(store, "/v1/responses", { model: "gpt-5.6-terra", input: "plan" });
    expect(reply.status).toBe(402);
    expect(reply.json().error.code).toBe("zoya_cap_reached");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("still lets the router model and Jev through over the cap, and meters them", async () => {
    const store = await fakeStore({ [GOOD]: license({ capCents: 1, spentCents: 5 }) });
    upstream({ answers: {}, usage: { inputTokens: 281, outputTokens: 21 } });
    const jev = await call(store, "/v1/evaluate", { model: "typesafe-ai/jev", state: "", questions: {} });
    upstream(CHAT_USAGE);
    const router = await call(store, "/v1/chat/completions", { model: "gpt-5.6-luna" });
    expect([jev.status, router.status]).toEqual([200, 200]);
    expect(store.recorded).toHaveLength(2);
  });
});

describe("license keys", () => {
  it.each([
    ["unknown", "zoya_nobody"],
    ["revoked", REVOKED],
    ["missing", ""],
  ])("rejects a %s key with a code the app recognises", async (_label, key) => {
    const store = await fakeStore({ [GOOD]: license(), [REVOKED]: license({ id: 2, active: false }) });
    const { fetchMock } = upstream(CHAT_USAGE);
    const reply = await call(store, "/v1/chat/completions", { model: "gpt-5.6-luna" }, key);
    expect(reply.status).toBe(401);
    expect(reply.json().error.code).toBe("zoya_license_invalid");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("the cost of a call", () => {
  it("prices uncached, cached and cache-write input and output separately", () => {
    const usage = usageFrom(CHAT_USAGE)!;
    const expectedUsd = (10 * 2.0 + 3 * 0.2 + 1800 * 2.0 * 1.25 + 10 * 12.0) / 1_000_000;
    expect(costCents("gpt-5.6-terra", usage)).toBeCloseTo(expectedUsd * 100, 10);
  });

  it("reads the Responses API's usage from a response.completed event", () => {
    const event = {
      type: "response.completed",
      response: { usage: { input_tokens: 100, output_tokens: 50, input_tokens_details: { cached_tokens: 40 } } },
    };
    expect(usageFrom(event)).toEqual({ input: 100, cached: 40, cacheWrite: 0, output: 50 });
  });

  it("prices Jev's input only", () => {
    const usage = usageFrom({ usage: { inputTokens: 281, outputTokens: 21 } })!;
    expect(costCents("typesafe-ai/jev", usage)).toBeCloseTo((281 * 0.042 * 100) / 1_000_000, 12);
  });

  it("records the cost of a streamed response from its final usage", async () => {
    const store = await fakeStore({ [GOOD]: license() });
    const stream = [
      `data: ${JSON.stringify({ choices: [{ delta: { content: "hi" } }], usage: null })}`,
      `data: ${JSON.stringify({ choices: [], ...CHAT_USAGE })}`,
      "data: [DONE]",
      "",
    ].join("\n\n");
    upstream(stream, "text/event-stream");
    const reply = await call(store, "/v1/chat/completions", { model: "gpt-5.6-terra", stream: true });
    expect(reply.text).toBe(stream);
    expect(store.recorded).toEqual([{ licenseId: 1, cents: costCents("gpt-5.6-terra", usageFrom(CHAT_USAGE)!) }]);
  });

  it("still records the cost when the client stops listening mid-stream", async () => {
    const store = await fakeStore({ [GOOD]: license() });
    upstream(`data: ${JSON.stringify({ choices: [], ...CHAT_USAGE })}\n\ndata: [DONE]\n\n`, "text/event-stream");
    const waits: Promise<unknown>[] = [];
    const request = new Request("https://relay.test/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${GOOD}` },
      body: JSON.stringify({ model: "gpt-5.6-terra", stream: true }),
    });
    const response = await handle(request, ENV, store, (p) => waits.push(p));
    await response.body!.cancel();
    await Promise.all(waits);
    expect(store.recorded).toHaveLength(1);
  });
});

describe("the model allowlist", () => {
  it.each([
    ["/v1/chat/completions", "gpt-5.6-sol"],
    ["/v1/responses", "o3-pro"],
    ["/v1/evaluate", "gpt-5.6-terra"],
    ["/v1/chat/completions", "typesafe-ai/jev"],
  ])("refuses %s with %s", async (path, model) => {
    const store = await fakeStore({ [GOOD]: license() });
    const { fetchMock } = upstream(CHAT_USAGE);
    const reply = await call(store, path, { model });
    expect(reply.status).toBe(403);
    expect(reply.json().error.code).toBe("zoya_model_not_allowed");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses built-in tools that bill per call", async () => {
    const store = await fakeStore({ [GOOD]: license() });
    upstream(CHAT_USAGE);
    const reply = await call(store, "/v1/responses", { model: "gpt-5.6-luna", tools: [{ type: "web_search" }] });
    expect(reply.json().error.code).toBe("zoya_tool_not_allowed");
  });

  it("answers any other path with a 404", async () => {
    const store = await fakeStore({ [GOOD]: license() });
    const reply = await call(store, "/v1/embeddings", { model: "gpt-5.6-luna" });
    expect(reply.status).toBe(404);
  });
});
