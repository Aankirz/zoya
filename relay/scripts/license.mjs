import { createHash, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { neon } from "@neondatabase/serverless";

const BETA_CAP_CENTS = 800;
const KEY_BYTES = 32;
const KINDS = new Set(["beta", "paid"]);
const USAGE = `usage:
  npm run license -- setup                       create the two tables
  npm run license -- issue <email> [beta|paid] [cap-cents]
  npm run license -- revoke <email|key>
  npm run license -- cap <email|key> <cents>
  npm run license -- usage <email|key>`;

const url = process.env.RELAY_DATABASE_URL;
if (!url) {
  console.error("RELAY_DATABASE_URL is not set (put it in the repo's .env).");
  process.exit(1);
}
const sql = neon(url);
const hash = (key) => createHash("sha256").update(key).digest("hex");
const matches = (who) => (who.includes("@") ? sql`email = ${who}` : sql`key_hash = ${hash(who)}`);

async function setup() {
  const schema = readFileSync(new URL("../schema.sql", import.meta.url), "utf8");
  for (const statement of schema.split(";").map((s) => s.trim()).filter(Boolean)) {
    await sql.query(statement);
  }
  console.log("tables ready");
}

async function issue(email, kind = "beta", cap = String(BETA_CAP_CENTS)) {
  if (!email?.includes("@") || !KINDS.has(kind) || !/^\d+$/.test(cap)) throw new Error(USAGE);
  const key = `zoya_${randomBytes(KEY_BYTES).toString("base64url")}`;
  await sql`insert into licenses (key_hash, email, kind, monthly_cap_cents)
            values (${hash(key)}, ${email}, ${kind}, ${Number(cap)})`;
  console.log(`issued a ${kind} key for ${email}, cap ${cap} cents a month. Shown once:\n${key}`);
}

async function revoke(who) {
  const rows = await sql`update licenses set active = false where ${matches(who)} returning email`;
  console.log(rows.length ? `revoked ${rows.length} key(s) for ${rows[0].email}` : "no such key");
}

async function cap(who, cents) {
  if (!/^\d+$/.test(cents ?? "")) throw new Error(USAGE);
  const rows = await sql`update licenses set monthly_cap_cents = ${Number(cents)}
                         where ${matches(who)} returning email`;
  console.log(rows.length ? `cap set to ${cents} cents for ${rows[0].email}` : "no such key");
}

async function usage(who) {
  const rows = await sql`select l.email, l.kind, l.active, l.monthly_cap_cents, u.month, u.cents, u.calls
                         from licenses l left join usage u on u.license_id = l.id
                         where ${matches(who)} order by u.month desc nulls last`;
  console.table(rows);
}

const commands = { setup, issue, revoke, cap, usage };
const [command, ...args] = process.argv.slice(2);
if (!commands[command] || (command !== "setup" && !args[0])) {
  console.error(USAGE);
  process.exit(1);
}
try {
  await commands[command](...args);
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
