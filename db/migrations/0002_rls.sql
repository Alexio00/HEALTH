begin;

alter table app_readers enable row level security;
alter table domains enable row level security;
alter table records enable row level security;
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

create or replace function public.is_app_reader()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.app_readers r
    where r.user_id = auth.uid()
  );
$$;

revoke all on function public.is_app_reader() from public;
grant execute on function public.is_app_reader() to authenticated;

create policy app_readers_self_select
  on app_readers for select to authenticated
  using (user_id = auth.uid());

create policy domains_reader_select
  on domains for select to authenticated
  using (public.is_app_reader());

create policy records_reader_select
  on records for select to authenticated
  using (public.is_app_reader());

create policy record_domains_reader_select
  on record_domains for select to authenticated
  using (public.is_app_reader());

create policy sources_reader_select
  on sources for select to authenticated
  using (public.is_app_reader());

create policy source_locations_reader_select
  on source_locations for select to authenticated
  using (public.is_app_reader());

create policy record_sources_reader_select
  on record_sources for select to authenticated
  using (public.is_app_reader());

create policy cases_reader_select
  on cases for select to authenticated
  using (public.is_app_reader());

create policy case_links_reader_select
  on case_links for select to authenticated
  using (public.is_app_reader());

create policy analytes_reader_select
  on analytes for select to authenticated
  using (public.is_app_reader());

create policy labs_reader_select
  on labs for select to authenticated
  using (public.is_app_reader());

create policy medications_reader_select
  on medications for select to authenticated
  using (public.is_app_reader());

create policy monitoring_reader_select
  on monitoring for select to authenticated
  using (public.is_app_reader());

create policy plan_items_reader_select
  on plan_items for select to authenticated
  using (public.is_app_reader());

create policy questions_reader_select
  on questions for select to authenticated
  using (public.is_app_reader());

revoke all on app_readers, domains, records, record_domains, sources,
  source_locations, record_sources, cases, case_links, analytes, labs,
  medications, monitoring, plan_items, questions,
  operations, id_reservations, validation_checks, validation_results, system_state from anon;

revoke all on operations, id_reservations, validation_checks, validation_results, system_state from authenticated;

revoke insert, update, delete on app_readers, domains, records, record_domains,
  sources, source_locations, record_sources, cases, case_links, analytes, labs,
  medications, monitoring, plan_items, questions from authenticated;

grant select on app_readers, domains, records, record_domains, sources,
  source_locations, record_sources, cases, case_links, analytes, labs,
  medications, monitoring, plan_items, questions to authenticated;

commit;
