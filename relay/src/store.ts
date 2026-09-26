import { neon } from "@neondatabase/serverless";
import type { License, Store } from "./relay";

export function neonStore(url: string): Store {
  const sql = neon(url);
  return {
    async find(keyHash, month) {
      const rows = await sql`
        select l.id, l.active, l.monthly_cap_cents, coalesce(u.cents, 0) as cents
        from licenses l
        left join usage u on u.license_id = l.id and u.month = ${month}
        where l.key_hash = ${keyHash}`;
      const row = rows[0];
      if (!row) return null;
      const license: License = {
        id: Number(row.id),
        active: Boolean(row.active),
        capCents: Number(row.monthly_cap_cents),
        spentCents: Number(row.cents),
      };
      return license;
    },
    async record(licenseId, month, cents) {
      await sql`
        insert into usage (license_id, month, cents, calls)
        values (${licenseId}, ${month}, ${cents}, 1)
        on conflict (license_id, month)
        do update set cents = usage.cents + excluded.cents, calls = usage.calls + 1`;
    },
  };
}
