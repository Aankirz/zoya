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
