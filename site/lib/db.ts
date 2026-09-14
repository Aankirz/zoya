import { neon } from "@neondatabase/serverless";

// Neon Postgres over HTTP. Returns null when DATABASE_URL is unset (local dev, or a build without env vars).
export function database() {
  const url = process.env.DATABASE_URL;
  return url ? neon(url) : null;
}
