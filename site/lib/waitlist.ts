import { appendFile, mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { database } from "./db";

const LOCAL_FILE = path.join(process.cwd(), "data", "waitlist.jsonl");

// Adds an already-validated email. Duplicates count as success.
export async function addToWaitlist(email: string): Promise<void> {
  const sql = database();
  if (sql) {
    await sql`insert into waitlist (email) values (${email}) on conflict (email) do nothing`;
    return;
  }
  if (process.env.VERCEL) throw new Error("DATABASE_URL is not set on this deployment");
  await addToLocalFile(email);
}

// Local dev only: the Vercel filesystem is read-only and ephemeral.
async function addToLocalFile(email: string): Promise<void> {
  const existing = await readFile(LOCAL_FILE, "utf8").catch(() => "");
  const lines = existing.split("\n").filter(Boolean);
  if (lines.some((line) => (JSON.parse(line) as { email: string }).email === email)) return;
  await mkdir(path.dirname(LOCAL_FILE), { recursive: true });
  await appendFile(LOCAL_FILE, `${JSON.stringify({ email, created_at: new Date().toISOString() })}\n`);
}
