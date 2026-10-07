begin;

-- Opt in to explicit Data API exposure for future objects created by postgres.
alter default privileges for role postgres in schema public
  revoke select, insert, update, delete on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke usage, select on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke execute on functions from anon, authenticated, public;

-- RLS on every table in the exposed public schema, including technical tables.
alter table operations enable row level security;
alter table app_readers enable row level security;
alter table domains enable row level security;
alter table records enable row level security;
alter table id_reservations enable row level security;
alter table record_domains enable row level security;
alter table sources enable row level security;
alter table source_locations enable row level security;
alter table record_sources enable row level security;
alter table cases enable row level security;
alter table case_links enable row level security;
alter table analytes enable row level security;
alter table labs enable row level security;
alter table medications enable row level security;
alter table monitoring enable row level security;
alter table plan_items enable row level security;
alter table questions enable row level security;
alter table validation_checks enable row level security;
alter table validation_results enable row level security;
alter table system_state enable row level security;

-- The authenticated browser may only recognize itself as an approved reader.
create policy app_readers_self_select
  on app_readers for select to authenticated
  using ((select auth.uid()) = user_id);

create policy domains_reader_select
  on domains for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy records_reader_select
  on records for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy record_domains_reader_select
  on record_domains for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy sources_reader_select
  on sources for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy source_locations_reader_select
  on source_locations for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy record_sources_reader_select
  on record_sources for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy cases_reader_select
  on cases for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy case_links_reader_select
  on case_links for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy analytes_reader_select
  on analytes for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy labs_reader_select
  on labs for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy medications_reader_select
  on medications for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy monitoring_reader_select
  on monitoring for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy plan_items_reader_select
  on plan_items for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

create policy questions_reader_select
  on questions for select to authenticated
  using ((exists (
    select 1
    from public.app_readers r
    where r.user_id = (select auth.uid())
  )));

-- Browser-facing tables: authenticated owner gets SELECT only.
revoke all on app_readers, domains, records, record_domains, sources,
  source_locations, record_sources, cases, case_links, analytes, labs,
  medications, monitoring, plan_items, questions from anon, public;

revoke insert, update, delete on app_readers, domains, records, record_domains,
  sources, source_locations, record_sources, cases, case_links, analytes, labs,
  medications, monitoring, plan_items, questions from authenticated;

grant select on app_readers, domains, records, record_domains, sources,
  source_locations, record_sources, cases, case_links, analytes, labs,
  medications, monitoring, plan_items, questions to authenticated;

-- Technical state is never exposed to browser roles.
revoke all on operations, id_reservations, validation_checks,
  validation_results, system_state from anon, authenticated, public;

commit;
