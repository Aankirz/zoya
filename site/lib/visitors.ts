import { database } from "./db";

function logFailure(action: string, error: unknown) {
  console.error(`visitors: ${action} failed:`, error instanceof Error ? error.message : error);
}

// Unique visitors so far, or null when there is no database or it can't be reached (the counter hides).
export async function getVisitorCount(): Promise<number | null> {
  const sql = database();
  if (!sql) return null;
  try {
    const rows = await sql`select count(*)::int as count from visitors`;
    return rows[0].count as number;
  } catch (error) {
    logFailure("count", error);
    return null;
  }
}

export async function recordVisitor(id: string): Promise<number | null> {
  const sql = database();
  if (!sql) return null;
  try {
    await sql`insert into visitors (id) values (${id}) on conflict (id) do nothing`;
  } catch (error) {
    logFailure("insert", error);
    return null;
  }
  return getVisitorCount();
}
