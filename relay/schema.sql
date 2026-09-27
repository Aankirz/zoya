create table if not exists licenses (
  id bigint generated always as identity primary key,
  key_hash text not null unique,
  email text not null,
  kind text not null check (kind in ('beta', 'paid')),
  active boolean not null default true,
  monthly_cap_cents integer not null check (monthly_cap_cents >= 0),
  created timestamptz not null default now()
);

create table if not exists usage (
  license_id bigint not null references licenses (id),
  month text not null,
  cents numeric(14, 6) not null default 0,
  calls integer not null default 0,
  primary key (license_id, month)
);

alter table licenses alter column email drop not null;

alter table licenses add column if not exists dodo_grant_id text;

alter table licenses add column if not exists dodo_customer_id text;

alter table licenses add column if not exists dodo_event_at timestamptz;

create table if not exists dodo_events (
  webhook_id text primary key,
  type text not null,
  received timestamptz not null default now()
);
