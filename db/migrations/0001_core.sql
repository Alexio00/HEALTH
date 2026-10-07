begin;

create extension if not exists pgcrypto;

create table operations (
  operation_id uuid primary key default gen_random_uuid(),
  operation text not null,
  mode text not null check (mode in ('maintenance','import')),
  scope text[] not null default '{}'::text[],
  state text not null check (state in ('PREPARED','COMMITTED_REGISTRY','VALIDATED','FINALIZED','FAILED')),
  result text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  finalized_at timestamptz
);

create unique index operations_single_writer_idx
  on operations ((true))
  where state in ('PREPARED','COMMITTED_REGISTRY','VALIDATED');

create table app_readers (
  user_id uuid primary key,
  label text,
  created_at timestamptz not null default now()
);

create table domains (
  domain_code text primary key,
  label text not null,
  active boolean not null default true,
  aliases text[] not null default '{}'::text[],
  metadata jsonb not null default '{}'::jsonb
);

create table records (
  record_id text primary key
    check (record_id ~ '^REC-[0-9]{8}-[0-9]{3}$'),
  nnn integer not null unique check (nnn between 1 and 999),
  record_date date not null,
  title text not null,
  type text,
  record_type text,
  confidence text,
  status text,
  tags text[] not null default '{}'::text[],
  summary text,
  body_text text not null,
  provenance_status text not null,
  source_label text,
  source_request_id text,
  source_pages text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table id_reservations (
  nnn integer primary key check (nnn between 1 and 999),
  state text not null check (state in ('used','reserved','retired')),
  record_id text unique references records(record_id) on delete restrict,
  operation_id uuid references operations(operation_id) on delete restrict,
  reserved_at timestamptz,
  updated_at timestamptz not null default now(),
  constraint id_reservations_state_shape check (
    (state = 'used' and record_id is not null) or
    (state = 'reserved' and operation_id is not null and record_id is null) or
    (state = 'retired' and record_id is null)
  )
);

create table record_domains (
  record_id text not null references records(record_id) on delete cascade,
  domain_code text not null references domains(domain_code) on delete restrict,
  primary key (record_id, domain_code)
);

create table sources (
  source_id text primary key
    check (source_id ~ '^SRC-[0-9]{8}-[0-9]{3,}$'),
  logical_path text not null unique,
  original_filename text not null,
  mime_type text,
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  sha256 text check (sha256 is null or sha256 ~ '^[0-9a-fA-F]{64}$'),
  source_date date,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table source_locations (
  source_id text not null references sources(source_id) on delete cascade,
  provider text not null,
  account_alias text not null,
  provider_object_id text not null,
  location_role text not null check (location_role in ('PRIMARY','BACKUP')),
  created_at timestamptz not null default now(),
  verified_at timestamptz,
  primary key (source_id, provider, account_alias, location_role),
  unique (provider, account_alias, provider_object_id)
);

create table record_sources (
  record_id text not null references records(record_id) on delete cascade,
  source_id text not null references sources(source_id) on delete restrict,
  role text not null default 'evidence',
  source_pages text,
  provenance jsonb not null default '{}'::jsonb,
  primary key (record_id, source_id, role)
);

create table cases (
  case_key text primary key references records(record_id) on delete restrict,
  opening_record_id text not null unique references records(record_id) on delete restrict,
  closing_record_id text references records(record_id) on delete restrict,
  category text not null check (category in ('chronic','episode')),
  status text not null check (status in ('open','closed')),
  title text not null,
  summary text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint cases_opening_identity check (case_key = opening_record_id),
  constraint cases_closing_shape check (
    (status = 'open' and closing_record_id is null) or
    (status = 'closed' and closing_record_id is not null)
  )
);

create table case_links (
  case_key text not null references cases(case_key) on delete cascade,
  record_id text not null references records(record_id) on delete cascade,
  relation text not null check (relation in ('OPEN','CONTINUES','CLOSES','FOLLOWUP')),
  created_at timestamptz not null default now(),
  primary key (case_key, record_id, relation)
);

create unique index case_links_one_open_idx
  on case_links (case_key)
  where relation = 'OPEN';

create unique index case_links_one_close_idx
  on case_links (case_key)
  where relation = 'CLOSES';

create table analytes (
  analyte_key text primary key,
  display_name text not null,
  aliases text[] not null default '{}'::text[],
  metadata jsonb not null default '{}'::jsonb
);

create table labs (
  lab_id bigint generated always as identity primary key,
  record_id text not null references records(record_id) on delete cascade,
  analyte_key text not null references analytes(analyte_key) on delete restrict,
  value text not null,
  unit text,
  reference_range text,
  flag text,
  observed_at timestamptz,
  source_id text references sources(source_id) on delete restrict,
  source_locator text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index labs_record_idx on labs(record_id);
create index labs_analyte_idx on labs(analyte_key, observed_at);

create table medications (
  medication_id bigint generated always as identity primary key,
  name text not null,
  status text not null check (status in ('active','inactive')),
  dose text,
  schedule text,
  started_on date,
  ended_on date,
  basis_record_id text references records(record_id) on delete restrict,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table monitoring (
  monitoring_id bigint generated always as identity primary key,
  title text not null,
  status text not null check (status in ('active','completed','cancelled')),
  cadence_text text,
  basis_record_id text references records(record_id) on delete restrict,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table plan_items (
  plan_item_id bigint generated always as identity primary key,
  title text not null,
  status text not null check (status in ('planned','done','cancelled')),
  due_on date,
  basis_record_id text references records(record_id) on delete restrict,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table questions (
  question_id bigint generated always as identity primary key,
  question text not null,
  status text not null check (status in ('open','closed')),
  basis_record_id text references records(record_id) on delete restrict,
  resolved_by_record_id text references records(record_id) on delete restrict,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint questions_resolution_shape check (
    (status = 'open' and resolved_by_record_id is null) or
    (status = 'closed')
  )
);

create table validation_checks (
  check_key text primary key,
  mechanism text not null check (mechanism in ('FORMULA','OPERATION_AUDIT')),
  description text not null,
  dependencies text[] not null default '{}'::text[],
  active boolean not null default true
);

create table validation_results (
  operation_id uuid not null references operations(operation_id) on delete cascade,
  check_key text not null references validation_checks(check_key) on delete restrict,
  status text not null check (status in ('PASS','FAIL','SKIP')),
  checked_at timestamptz not null default now(),
  details jsonb not null default '{}'::jsonb,
  primary key (operation_id, check_key)
);

create table system_state (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

commit;
