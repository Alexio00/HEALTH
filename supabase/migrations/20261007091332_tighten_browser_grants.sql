revoke all privileges on table
  public.app_readers, public.domains, public.records, public.record_domains,
  public.sources, public.source_locations, public.record_sources, public.cases,
  public.case_links, public.analytes, public.labs, public.medications,
  public.monitoring, public.plan_items, public.questions
from authenticated;

grant select on table
  public.app_readers, public.domains, public.records, public.record_domains,
  public.sources, public.source_locations, public.record_sources, public.cases,
  public.case_links, public.analytes, public.labs, public.medications,
  public.monitoring, public.plan_items, public.questions
to authenticated;

revoke all privileges on all sequences in schema public from anon, authenticated;
