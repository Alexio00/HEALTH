-- HEALTH vaccination registry — PROPOSAL ONLY, NOT A PRODUCTION MIGRATION.
-- Approved conceptual model: issue #41. Do not execute directly against
-- canonical Supabase or merge to main without Writer integration and review.
-- This file contains schema/privilege design only, never clinical rows.
begin;

create table public.vaccination_courses (
  course_id uuid primary key default gen_random_uuid(),
  course_kind text not null default 'unknown'
    check (course_kind in ('primary','booster','seasonal','unknown')),
  course_label text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.vaccination_antigens (
  antigen_key text primary key
    check (antigen_key ~ '^[a-z][a-z0-9_-]*$'),
  display_name text not null check (btrim(display_name) <> ''),
  created_at timestamptz not null default now()
);

create table public.vaccination_administrations (
  administration_id uuid primary key default gen_random_uuid(),
  course_id uuid references public.vaccination_courses(course_id) on delete restrict,
  administered_on date,
  product_name text,
  verification_status text not null default 'pending'
    check (verification_status in ('pending','verified','retracted')),
  stage_kind text not null default 'unknown'
    check (stage_kind in ('dose','revaccination','unknown')),
  dose_number integer check (dose_number between 1 and 999),
  stage_source_text text,
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- dose + number => V1/V2; revaccination + NULL => Rv;
  -- revaccination + number => Rv1/Rv2. Unknown stage has no number.
  -- Preserve the literal source label separately in stage_source_text.
  constraint vaccination_administrations_stage_shape
    check (stage_kind <> 'unknown' or dose_number is null),
  constraint vaccination_administrations_verified_date
    check (verification_status <> 'verified' or administered_on is not null)
);

create index vaccination_administrations_course_idx
  on public.vaccination_administrations(course_id);
create index vaccination_administrations_date_idx
  on public.vaccination_administrations(administered_on desc);

create table public.vaccination_administration_antigens (
  administration_id uuid not null references
    public.vaccination_administrations(administration_id) on delete restrict,
  antigen_key text not null references public.vaccination_antigens(antigen_key)
    on delete restrict,
  primary key(administration_id,antigen_key)
);
create index vaccination_administration_antigens_key_idx
  on public.vaccination_administration_antigens(antigen_key);

create table public.vaccination_evidence (
  evidence_id bigint generated always as identity primary key,
  administration_id uuid not null references
    public.vaccination_administrations(administration_id) on delete restrict,
  record_id text not null references public.records(record_id) on delete restrict,
  source_id text references public.sources(source_id) on delete restrict,
  source_pages text,
  evidence_role text not null
    check (evidence_role in ('administered','prescribed','supporting')),
  verification_note text,
  created_at timestamptz not null default now()
);
create unique index vaccination_evidence_unique_idx
  on public.vaccination_evidence
  (administration_id,record_id,evidence_role,source_id) nulls not distinct;
create index vaccination_evidence_record_idx
  on public.vaccination_evidence(record_id);
create index vaccination_evidence_source_idx
  on public.vaccination_evidence(source_id);

create table public.vaccination_plan_links (
  administration_id uuid not null references
    public.vaccination_administrations(administration_id) on delete restrict,
  plan_item_id bigint not null references public.plan_items(plan_item_id)
    on delete restrict,
  link_kind text not null check (link_kind in ('related','fulfills')),
  created_at timestamptz not null default now(),
  primary key(administration_id,plan_item_id)
);
create index vaccination_plan_links_plan_idx
  on public.vaccination_plan_links(plan_item_id);

-- Exposed public schema: fail-closed RLS on all six new tables.
alter table public.vaccination_courses enable row level security;
alter table public.vaccination_antigens enable row level security;
alter table public.vaccination_administrations enable row level security;
alter table public.vaccination_administration_antigens enable row level security;
alter table public.vaccination_evidence enable row level security;
alter table public.vaccination_plan_links enable row level security;

-- No browser, anonymous or service_role mutations.
revoke all on table
  public.vaccination_courses,public.vaccination_antigens,
  public.vaccination_administrations,
  public.vaccination_administration_antigens,
  public.vaccination_evidence,public.vaccination_plan_links
from public,anon,authenticated,service_role;

grant select on table
  public.vaccination_courses,public.vaccination_antigens,
  public.vaccination_administrations,
  public.vaccination_administration_antigens,
  public.vaccination_evidence,public.vaccination_plan_links
to authenticated;

-- Service role may read for audit; no INSERT/UPDATE/DELETE.
grant select on table
  public.vaccination_courses,public.vaccination_antigens,
  public.vaccination_administrations,
  public.vaccination_administration_antigens,
  public.vaccination_evidence,public.vaccination_plan_links
to service_role;

revoke all on sequence public.vaccination_evidence_evidence_id_seq
  from public,anon,authenticated,service_role;

create policy vaccination_courses_reader on public.vaccination_courses
for select to authenticated
using (exists(select 1 from public.app_readers r where r.user_id=(select auth.uid())));
create policy vaccination_antigens_reader on public.vaccination_antigens
for select to authenticated
using (exists(select 1 from public.app_readers r where r.user_id=(select auth.uid())));
create policy vaccination_administrations_reader on public.vaccination_administrations
for select to authenticated
using (exists(select 1 from public.app_readers r where r.user_id=(select auth.uid())));
create policy vaccination_administration_antigens_reader on public.vaccination_administration_antigens
for select to authenticated
using (exists(select 1 from public.app_readers r where r.user_id=(select auth.uid())));
create policy vaccination_evidence_reader on public.vaccination_evidence
for select to authenticated
using (exists(select 1 from public.app_readers r where r.user_id=(select auth.uid())));
create policy vaccination_plan_links_reader on public.vaccination_plan_links
for select to authenticated
using (exists(select 1 from public.app_readers r where r.user_id=(select auth.uid())));
commit;

-- DEFERRED until the bounded Writer contract is updated:
-- 1) only authenticated and separately verified Writer candidates may create
--    verified administrations; SQL shape checks alone do not prove administration.
-- 2) verified administrations must have >= 1 "administered" REC evidence,
--    >= 1 antigen and proven event date. Validate source linkage, course/dose
--    semantics, revoked duplicates and every plan link during publish.
-- 3) runtime privilege grants must be scoped to reviewed Writer RPCs, not
--    broad public/service_role UPDATE or direct browser INSERT.
-- 4) zero historical vaccinations are inserted by this schema proposal.
