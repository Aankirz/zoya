// Pure validators shared by the browser and the API routes. No imports, so `node --test` runs them directly.

const MAX_EMAIL_LENGTH = 254;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function normalizeEmail(input: unknown): string | null {
  if (typeof input !== "string") return null;
  const email = input.trim().toLowerCase();
  if (email.length > MAX_EMAIL_LENGTH) return null;
  return EMAIL_PATTERN.test(email) ? email : null;
}

export function isVisitorId(input: unknown): input is string {
  return typeof input === "string" && UUID_PATTERN.test(input);
}
