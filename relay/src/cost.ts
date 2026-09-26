export type Usage = { input: number; cached: number; cacheWrite: number; output: number };

type Price = { input: number; cached: number; output: number; upstream: "openai" | "jev" };

export const PRICES_USD_PER_1M: Record<string, Price> = {
  "gpt-5.6-terra": { input: 2.0, cached: 0.2, output: 12.0, upstream: "openai" },
  "gpt-5.6-luna": { input: 0.2, cached: 0.02, output: 1.2, upstream: "openai" },
  "typesafe-ai/jev": { input: 0.042, cached: 0.042, output: 0, upstream: "jev" },
};

export const HEAVY_MODELS = new Set(["gpt-5.6-terra"]);

const TOKENS_PER_PRICE_UNIT = 1_000_000;
const CENTS_PER_USD = 100;
const CACHE_WRITE_MULTIPLIER = 1.25;
const LONG_PROMPT_TOKENS = 272_000;
const LONG_PROMPT_INPUT_MULTIPLIER = 2;
const LONG_PROMPT_OUTPUT_MULTIPLIER = 1.5;

export function costCents(model: string, usage: Usage): number {
  const price = PRICES_USD_PER_1M[model];
  if (!price) throw new Error(`no price for ${model}`);
  const long = price.upstream === "openai" && usage.input > LONG_PROMPT_TOKENS;
  const inputScale = long ? LONG_PROMPT_INPUT_MULTIPLIER : 1;
  const outputScale = long ? LONG_PROMPT_OUTPUT_MULTIPLIER : 1;
  const uncached = Math.max(0, usage.input - usage.cached - usage.cacheWrite);
  const inputUsd =
    uncached * price.input +
    usage.cached * price.cached +
    usage.cacheWrite * price.input * CACHE_WRITE_MULTIPLIER;
  const usd = inputUsd * inputScale + usage.output * price.output * outputScale;
  return (usd / TOKENS_PER_PRICE_UNIT) * CENTS_PER_USD;
}

type Json = Record<string, unknown>;

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : 0;
}

function field(value: unknown, key: string): Json {
  const inner = (value as Json | undefined)?.[key];
  return inner && typeof inner === "object" ? (inner as Json) : {};
}

export function usageFrom(body: unknown): Usage | null {
  const usage = field(body, "usage");
  const nested = field(field(body, "response"), "usage");
  const found = Object.keys(usage).length ? usage : nested;
  if (!Object.keys(found).length) return null;
  const details = { ...field(found, "prompt_tokens_details"), ...field(found, "input_tokens_details") };
  return {
    input: count(found.prompt_tokens ?? found.input_tokens ?? found.inputTokens),
    cached: count(details.cached_tokens),
    cacheWrite: count(details.cache_write_tokens),
    output: count(found.completion_tokens ?? found.output_tokens ?? found.outputTokens),
  };
}
