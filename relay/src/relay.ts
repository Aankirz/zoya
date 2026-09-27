import { HEAVY_MODELS, OVERALL_CEILING_MULTIPLIER, PRICES_USD_PER_1M, costCents, usageFrom, type Usage } from "./cost";
import { DODO_WEBHOOK_PATH, handleDodo } from "./dodo";
import { amzDate, signedPostHeaders } from "./sigv4";

export type License = { id: number; active: boolean; capCents: number; spentCents: number };
export type KeyChange = { keyHash: string; grantId: string; customerId: string; active: boolean; at: string };

export interface Store {
  find(keyHash: string, month: string): Promise<License | null>;
  record(licenseId: number, month: string, cents: number): Promise<void>;
  seen(webhookId: string): Promise<boolean>;
  recordEvent(webhookId: string, type: string, change: KeyChange | null): Promise<void>;
}

export type Env = {
  OPENAI_API_KEY: string;
  AI_GATEWAY_API_KEY: string;
  RELAY_DATABASE_URL: string;
  OPENAI_BASE_URL: string;
  AI_GATEWAY_BASE_URL: string;
  AWS_ACCESS_KEY_ID: string;
  AWS_SECRET_ACCESS_KEY: string;
  AWS_SESSION_TOKEN?: string;
  POLLY_REGION: string;
  DODO_WEBHOOK_SECRET: string;
  DODO_API_KEY: string;
  DODO_API_BASE_URL: string;
};

type Upstream = "openai" | "jev" | "polly";
type Json = Record<string, unknown>;
type Call = { fingerprint: string; path: string; model: string; started: number };

export const ROUTES: Record<string, Upstream> = {
  "/v1/chat/completions": "openai",
  "/v1/responses": "openai",
  "/v1/evaluate": "jev",
  "/v1/speech": "polly",
};
const UPSTREAM_PATH: Record<string, string> = {
  "/v1/chat/completions": "/chat/completions",
  "/v1/responses": "/responses",
  "/v1/evaluate": "/evaluate",
};
const LICENSE_PATH = "/v1/license";
const FINGERPRINT_CHARS = 8;
const USAGE_FIELD = /"usage"\s*:\s*\{/;
const SSE_DATA = "data:";
const SERVER_MODELS: Partial<Record<Upstream, string>> = { polly: "amazon-polly-neural" };
const SPEECH_VOICES = new Set(["Kajal"]);
const SPEECH_LANGUAGES = new Set(["en-IN", "hi-IN"]);
const SPEECH_SAMPLE_RATES = new Set(["8000", "16000"]);
const MAX_SPEECH_CHARS = 3000;

export function fail(status: number, code: string, message: string): Response {
  return Response.json({ error: { message, type: "zoya_relay_error", code } }, { status });
}

export async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function monthOf(date: Date): string {
  return date.toISOString().slice(0, 7);
}

function bearer(request: Request): string {
  const header = request.headers.get("Authorization") ?? "";
  return header.startsWith("Bearer ") ? header.slice("Bearer ".length).trim() : "";
}

async function readJson(request: Request): Promise<Json | null> {
  try {
    const body: unknown = await request.json();
    return body && typeof body === "object" && !Array.isArray(body) ? (body as Json) : null;
  } catch {
    return null;
  }
}

export function meteredModel(upstream: Upstream, body: Json): string {
  return SERVER_MODELS[upstream] ?? (typeof body.model === "string" ? body.model : "");
}

function refusal(upstream: Upstream, model: string, body: Json): Response | null {
  if (PRICES_USD_PER_1M[model]?.upstream !== upstream) {
    return fail(403, "zoya_model_not_allowed", `The model ${model || "(none)"} is not available.`);
  }
  if (upstream === "polly") return speechRefusal(body);
  const tools = Array.isArray(body.tools) ? body.tools : [];
  if (tools.some((tool) => (tool as Json | null)?.type !== "function")) {
    return fail(403, "zoya_tool_not_allowed", "Only function tools are available.");
  }
  return null;
}

function speechRefusal(body: Json): Response | null {
  const text = typeof body.text === "string" ? body.text : "";
  const valid =
    text.trim().length > 0 &&
    text.length <= MAX_SPEECH_CHARS &&
    SPEECH_VOICES.has(String(body.voice)) &&
    SPEECH_LANGUAGES.has(String(body.language)) &&
    SPEECH_SAMPLE_RATES.has(String(body.sample_rate));
  return valid ? null : fail(400, "zoya_speech_invalid", "That speech request is not available.");
}

export function rewrite(path: string, body: Json): Json {
  if (ROUTES[path] !== "openai") return body;
  const sent: Json = { ...body, store: false };
  if (path === "/v1/chat/completions" && "max_tokens" in body) {
    const { max_tokens, ...rest } = sent;
    return rewrite(path, { max_completion_tokens: max_tokens, ...rest });
  }
  if (path === "/v1/chat/completions" && Array.isArray(body.tools) && body.tools.length && !("reasoning_effort" in body)) {
    sent.reasoning_effort = "none";
  }
  if (path === "/v1/chat/completions" && body.stream === true) {
    const options = body.stream_options && typeof body.stream_options === "object" ? body.stream_options : {};
    sent.stream_options = { ...options, include_usage: true };
  }
  return sent;
}

function target(env: Env, path: string): { url: string; key: string } {
  const jev = ROUTES[path] === "jev";
  const base = (jev ? env.AI_GATEWAY_BASE_URL : env.OPENAI_BASE_URL).replace(/\/$/, "");
  return { url: base + UPSTREAM_PATH[path], key: jev ? env.AI_GATEWAY_API_KEY : env.OPENAI_API_KEY };
}

async function authorise(request: Request, store: Store): Promise<{ license: License; fingerprint: string } | Response> {
  const key = bearer(request);
  if (!key) return fail(401, "zoya_license_invalid", "A Zoya license key is required.");
  const hash = await sha256Hex(key);
  const fingerprint = hash.slice(0, FINGERPRINT_CHARS);
  let license: License | null;
  try {
    license = await store.find(hash, monthOf(new Date()));
  } catch (error) {
    log({ fingerprint, event: "store_unavailable", error: errorName(error) });
    return fail(503, "zoya_relay_unavailable", "Zoya's service is unavailable right now.");
  }
  if (!license || !license.active) {
    log({ fingerprint, event: "license_invalid", status: 401 });
    return fail(401, "zoya_license_invalid", "This Zoya license key is not valid.");
  }
  return { license, fingerprint };
}

export async function handle(request: Request, env: Env, store: Store, waitUntil: (p: Promise<unknown>) => void): Promise<Response> {
  const path = new URL(request.url).pathname;
  if (path === LICENSE_PATH && request.method === "GET") return checkLicense(request, store);
  if (path === DODO_WEBHOOK_PATH && request.method === "POST") return handleDodo(request, env, store);
  const upstream = ROUTES[path];
  if (!upstream || request.method !== "POST") return fail(404, "not_found", "Not found.");
  const auth = await authorise(request, store);
  if (auth instanceof Response) return auth;
  const body = await readJson(request);
  if (!body) return fail(400, "invalid_json", "The request body must be a JSON object.");
  const model = meteredModel(upstream, body);
  const refused = refusal(upstream, model, body);
  const call: Call = { fingerprint: auth.fingerprint, path, model, started: Date.now() };
  if (refused) {
    log({ ...describe(call), status: refused.status });
    return refused;
  }
  if (overCap(auth.license, model)) {
    log({ ...describe(call), status: 402, event: "cap_reached" });
    return fail(402, "zoya_cap_reached", "This month's allowance for heavy tasks is used up.");
  }
  const meter = (usage: Usage | null, status: number) => settle(call, auth.license, usage, status, store);
  if (upstream === "polly") return speak(env, body, call, meter, waitUntil);
  return forward(env, path, rewrite(path, body), call, meter, waitUntil);
}

async function checkLicense(request: Request, store: Store): Promise<Response> {
  const auth = await authorise(request, store);
  if (auth instanceof Response) return auth;
  log({ fingerprint: auth.fingerprint, path: LICENSE_PATH, status: 200 });
  const { spentCents, capCents } = auth.license;
  return Response.json({ valid: true, month: monthOf(new Date()), usedCents: Math.round(spentCents * 100) / 100, capCents });
}

function overCap(license: License, model: string): boolean {
  const limit = HEAVY_MODELS.has(model) ? license.capCents : license.capCents * OVERALL_CEILING_MULTIPLIER;
  return license.spentCents >= limit;
}

async function forward(
  env: Env,
  path: string,
  body: Json,
  call: Call,
  meter: (usage: Usage | null, status: number) => Promise<void>,
  waitUntil: (p: Promise<unknown>) => void,
): Promise<Response> {
  const { url, key } = target(env, path);
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    log({ ...describe(call), status: 502, event: "upstream_unreachable", error: errorName(error) });
    return fail(502, "zoya_upstream_unreachable", "The model provider could not be reached.");
  }
  const headers = { "Content-Type": response.headers.get("Content-Type") ?? "application/json" };
  if (headers["Content-Type"].includes("text/event-stream") && response.body) {
    const [toClient, toMeter] = response.body.tee();
    waitUntil(streamUsage(toMeter).then((usage) => meter(usage, response.status)));
    return new Response(toClient, { status: response.status, headers });
  }
  const text = await response.text();
  waitUntil(meter(usageFromText(text), response.status));
  return new Response(text, { status: response.status, headers });
}

async function speak(
  env: Env,
  body: Json,
  call: Call,
  meter: (usage: Usage | null, status: number) => Promise<void>,
  waitUntil: (p: Promise<unknown>) => void,
): Promise<Response> {
  const text = String(body.text);
  const polly = JSON.stringify({
    Engine: "neural",
    LanguageCode: body.language,
    OutputFormat: "pcm",
    SampleRate: body.sample_rate,
    Text: text,
    VoiceId: body.voice,
  });
  const url = `https://polly.${env.POLLY_REGION}.amazonaws.com/v1/speech`;
  const credentials = {
    accessKeyId: env.AWS_ACCESS_KEY_ID,
    secretAccessKey: env.AWS_SECRET_ACCESS_KEY,
    sessionToken: env.AWS_SESSION_TOKEN || undefined,
  };
  const signing = { url, body: polly, region: env.POLLY_REGION, service: "polly", amzDate: amzDate(new Date()) };
  const { host: _host, ...headers } = await signedPostHeaders(credentials, signing);
  let response: Response;
  try {
    response = await fetch(url, { method: "POST", headers, body: polly });
  } catch (error) {
    log({ ...describe(call), status: 502, event: "upstream_unreachable", error: errorName(error) });
    return fail(502, "zoya_upstream_unreachable", "The voice provider could not be reached.");
  }
  const characters = Number(response.headers.get("x-amzn-RequestCharacters")) || text.length;
  waitUntil(meter(response.ok ? { input: characters, cached: 0, cacheWrite: 0, output: 0 } : null, response.status));
  const contentType = response.headers.get("Content-Type") ?? "application/octet-stream";
  return new Response(response.body, { status: response.status, headers: { "Content-Type": contentType } });
}

function usageFromText(text: string): Usage | null {
  try {
    return usageFrom(JSON.parse(text));
  } catch {
    return null;
  }
}

export async function streamUsage(body: ReadableStream<Uint8Array>): Promise<Usage | null> {
  const decoder = new TextDecoder();
  let pending = "";
  let usage: Usage | null = null;
  const scan = (line: string) => {
    if (!line.startsWith(SSE_DATA) || !USAGE_FIELD.test(line)) return;
    usage = usageFromText(line.slice(SSE_DATA.length)) ?? usage;
  };
  for await (const chunk of body) {
    pending += decoder.decode(chunk, { stream: true });
    const lines = pending.split("\n");
    pending = lines.pop() ?? "";
    lines.forEach(scan);
  }
  scan(pending + decoder.decode());
  return usage;
}

async function settle(call: Call, license: License, usage: Usage | null, status: number, store: Store): Promise<void> {
  let cents = 0;
  try {
    cents = usage ? costCents(call.model, usage) : 0;
  } catch (error) {
    log({ ...describe(call), status, event: "unpriced_model", error: errorName(error) });
    return;
  }
  log({ ...describe(call), status, ...(usage ?? {}), cents: Number(cents.toFixed(6)), metered: usage !== null });
  if (!usage) return;
  try {
    await store.record(license.id, monthOf(new Date()), cents);
  } catch (error) {
    log({ fingerprint: call.fingerprint, event: "record_failed", cents, error: errorName(error) });
  }
}

function describe(call: Call): Json {
  return { fingerprint: call.fingerprint, path: call.path, model: call.model, ms: Date.now() - call.started };
}

function errorName(error: unknown): string {
  return error instanceof Error ? error.name : typeof error;
}

function log(entry: Json): void {
  console.log(JSON.stringify(entry));
}
