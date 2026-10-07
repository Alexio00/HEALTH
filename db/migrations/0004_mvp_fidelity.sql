begin;

alter table public.case_links
  add column relation_date date,
  add column note text;

alter table public.labs
  add column observed_on date,
  add column source_name text,
  add column note text;

create unique index labs_exact_source_row_idx
  on public.labs (
    record_id,
    observed_on,
    analyte_key,
    value,
    unit,
    reference_range,
    flag,
    source_name,
    note
  ) nulls not distinct;

commit;
