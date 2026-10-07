begin;
create policy app_readers_self_select on public.app_readers for select to authenticated
  using ((select auth.uid()) = user_id);

create policy domains_reader_select on public.domains for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy records_reader_select on public.records for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy record_domains_reader_select on public.record_domains for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy sources_reader_select on public.sources for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy source_locations_reader_select on public.source_locations for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy record_sources_reader_select on public.record_sources for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy cases_reader_select on public.cases for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy case_links_reader_select on public.case_links for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy analytes_reader_select on public.analytes for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy labs_reader_select on public.labs for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy medications_reader_select on public.medications for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy monitoring_reader_select on public.monitoring for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy plan_items_reader_select on public.plan_items for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
create policy questions_reader_select on public.questions for select to authenticated
  using (exists (select 1 from public.app_readers r where r.user_id = (select auth.uid())));
commit;
