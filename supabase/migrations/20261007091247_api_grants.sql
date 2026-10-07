begin;
revoke all on public.app_readers, public.domains, public.records, public.record_domains, public.sources,
  public.source_locations, public.record_sources, public.cases, public.case_links, public.analytes, public.labs,
  public.medications, public.monitoring, public.plan_items, public.questions from anon, public;

revoke insert, update, delete on public.app_readers, public.domains, public.records, public.record_domains,
  public.sources, public.source_locations, public.record_sources, public.cases, public.case_links, public.analytes,
  public.labs, public.medications, public.monitoring, public.plan_items, public.questions from authenticated;

grant select on public.app_readers, public.domains, public.records, public.record_domains, public.sources,
  public.source_locations, public.record_sources, public.cases, public.case_links, public.analytes, public.labs,
  public.medications, public.monitoring, public.plan_items, public.questions to authenticated;
commit;
