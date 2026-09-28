/// <reference types="node" />
import { readFileSync } from "node:fs";
import { PGlite } from "@electric-sql/pglite";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { KeyChange } from "../src/relay";
import { neonStore } from "../src/store";

// The real store SQL runs against Postgres (PGlite) through a stand-in for Neon's tagged-template client.
const pg = vi.hoisted(() => ({ db: null as unknown as PGlite }));

vi.mock("@neondatabase/serverless", () => {
  type Query = { text: string; values: unknown[]; then: Promise<unknown[]>["then"] };
  const query = (text: string, values: unknown[]): Query => ({
    text,
    values,
    then: (resolve, reject) => pg.db.query(text, values).then((result) => result.rows).then(resolve, reject),
  });
  const neon = () => {
    const sql = (strings: TemplateStringsArray, ...values: unknown[]) =>
      query(strings.reduce((text, part, i) => `${text}$${i}${part}`), values);
    sql.transaction = (queries: Query[]) =>
      pg.db.transaction(async (tx) => {
        for (const q of queries) await tx.query(q.text, q.values);
      });
    return sql;
  };
  return { neon };
});

const LEGACY_SCHEMA = [
  `create table licenses (
    id bigint generated always as identity primary key,
    key_hash text not null unique,
    email text not null,
    kind text not null check (kind in ('beta', 'paid')),
    active boolean not null default true,
    monthly_cap_cents integer not null check (monthly_cap_cents >= 0),
    created timestamptz not null default now()
  )`,
  `create table usage (
    license_id bigint not null references licenses (id),
    month text not null,
    cents numeric(14, 6) not null default 0,
    calls integer not null default 0,
    primary key (license_id, month)
  )`,
];
const MONTH = "2026-10";
const GRANT = "entg_1";
const T0 = "2026-10-01T10:00:00.000000Z";
const T1 = "2026-11-01T10:00:00.000000Z";
const T2 = "2026-11-03T10:00:00.000000Z";

async function migrate() {
  const schema = readFileSync(new URL("../schema.sql", import.meta.url), "utf8");
  for (const statement of schema.split(";").map((s) => s.trim()).filter(Boolean)) await pg.db.query(statement);
}

const change = (over: Partial<KeyChange>): KeyChange => ({
  keyHash: "hash_paid",
  grantId: GRANT,
  customerId: "cus_1",
  active: true,
  at: T0,
  ...over,
});

beforeAll(() => {
  pg.db = new PGlite();
});

beforeEach(async () => {
  await pg.db.exec("drop table if exists usage, licenses, dodo_events");
  for (const statement of LEGACY_SCHEMA) await pg.db.query(statement);
  await pg.db.query(`insert into licenses (key_hash, email, kind, monthly_cap_cents) values ('hash_beta', 'b@x.in', 'beta', 800)`);
  await migrate();
});

describe("schema migration", () => {
  it("runs again on an already-migrated database and leaves beta keys working", async () => {
    await migrate();
    const store = neonStore("postgres://test");
    expect(await store.find("hash_beta", MONTH)).toMatchObject({ active: true, capCents: 800 });
    const rows = await pg.db.query(`select email, kind from licenses where key_hash = 'hash_beta'`);
    expect(rows.rows).toEqual([{ email: "b@x.in", kind: "beta" }]);
  });
});

describe("neon store for Dodo events", () => {
  it("stores a paid key with the monthly cap and records the webhook", async () => {
    const store = neonStore("postgres://test");
    await store.recordEvent("msg_1", "entitlement_grant.created", change({}));
    expect(await store.find("hash_paid", MONTH)).toMatchObject({ active: true, capCents: 800 });
    expect(await store.seen("msg_1")).toBe(true);
  });

  it("an older event arriving late does not undo a newer one", async () => {
    const store = neonStore("postgres://test");
    await store.recordEvent("msg_revoked", "entitlement_grant.revoked", change({ active: false, at: T1 }));
    await store.recordEvent("msg_created", "entitlement_grant.created", change({ active: true, at: T0 }));
    expect((await store.find("hash_paid", MONTH))?.active).toBe(false);
  });

  it("a restore after a revoke reactivates the key", async () => {
    const store = neonStore("postgres://test");
    await store.recordEvent("msg_created", "entitlement_grant.created", change({ at: T0 }));
    await store.recordEvent("msg_revoked", "entitlement_grant.revoked", change({ active: false, at: T1 }));
    await store.recordEvent("msg_restored", "entitlement_grant.delivered", change({ active: true, at: T2 }));
    expect((await store.find("hash_paid", MONTH))?.active).toBe(true);
  });

  it("never changes a beta key, even one whose hash a Dodo event names", async () => {
    const store = neonStore("postgres://test");
    await store.recordEvent("msg_revoked", "entitlement_grant.revoked", change({ keyHash: "hash_beta", active: false, at: T1 }));
    const rows = await pg.db.query(`select kind, active, dodo_grant_id from licenses where key_hash = 'hash_beta'`);
    expect(rows.rows).toEqual([{ kind: "beta", active: true, dodo_grant_id: null }]);
  });

  it("a revoke that names only the grant deactivates that grant's paid key", async () => {
    const store = neonStore("postgres://test");
    await store.recordEvent("msg_created", "entitlement_grant.created", change({ at: T0 }));
    await store.recordEvent("msg_revoked", "entitlement_grant.revoked", change({ keyHash: null, active: false, at: T1 }));
    expect((await store.find("hash_paid", MONTH))?.active).toBe(false);
    expect((await store.find("hash_beta", MONTH))?.active).toBe(true);
    expect(await store.seen("msg_revoked")).toBe(true);
  });

  it("a grant-only event older than the last one applied is ignored", async () => {
    const store = neonStore("postgres://test");
    await store.recordEvent("msg_created", "entitlement_grant.created", change({ at: T0 }));
    await store.recordEvent("msg_revoked", "entitlement_grant.revoked", change({ keyHash: null, active: false, at: T2 }));
    await store.recordEvent("msg_restored", "entitlement_grant.delivered", change({ keyHash: null, active: true, at: T1 }));
    expect((await store.find("hash_paid", MONTH))?.active).toBe(false);
  });
});
