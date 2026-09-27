import { neon } from "@neondatabase/serverless";
import type { License, Store } from "./relay";

const PAID_CAP_CENTS = 800;

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
    async seen(webhookId) {
      const rows = await sql`select 1 from dodo_events where webhook_id = ${webhookId}`;
      return rows.length > 0;
    },
    async recordEvent(webhookId, type, change) {
      const event = sql`
        insert into dodo_events (webhook_id, type) values (${webhookId}, ${type})
        on conflict (webhook_id) do nothing`;
      if (!change) {
        await event;
        return;
      }
      const license = sql`
        insert into licenses (key_hash, kind, active, monthly_cap_cents, dodo_grant_id, dodo_customer_id, dodo_event_at)
        values (${change.keyHash}, 'paid', ${change.active}, ${PAID_CAP_CENTS}, ${change.grantId}, ${change.customerId}, ${change.at})
        on conflict (key_hash) do update
        set active = excluded.active, dodo_event_at = excluded.dodo_event_at
        where licenses.kind = 'paid'
          and (licenses.dodo_event_at is null or licenses.dodo_event_at <= excluded.dodo_event_at)`;
      await sql.transaction([license, event]);
    },
  };
}
