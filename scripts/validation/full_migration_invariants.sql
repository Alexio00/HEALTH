-- Full migration post-load validation.
-- Zero medical content is embedded in this script.
--
-- Before use, the migration operation must create private system_state key:
-- full_migration_snapshot
-- {
--   "status": "CAPTURED",
--   "expected_counts": {
--     "records": ...,
--     "domains": ...,
--     "record_domains": ...,
--     "sources": ...,
--     "source_locations": ...,
--     "record_sources": ...,
--     "cases": ...,
--     "case_links": ...,
--     "analytes": ...,
--     "labs": ...,
--     "medications": ...,
--     "monitoring": ...,
--     "plan_items": ...,
--     "questions": ...,
--     "id_reservations": ...
--   },
--   "historical_sources_manifest_sha256": "..."
-- }
--
-- PASS = invariant proven.
-- FAIL = invariant violated.
-- WAITING = final snapshot has not been captured yet.

with snapshot as (
  select value
  from public.system_state
  where key = 'full_migration_snapshot'
),
expected as (
  select value->'expected_counts' counts
  from snapshot
  where value->>'status' = 'CAPTURED'
),
count_checks as (
  select 'COUNT_RECORDS' check_key,
         (select count(*) from public.records) =
         (select (counts->>'records')::bigint from expected) pass
  union all
  select 'COUNT_DOMAINS',
         (select count(*) from public.domains) =
         (select (counts->>'domains')::bigint from expected)
  union all
  select 'COUNT_RECORD_DOMAINS',
         (select count(*) from public.record_domains) =
         (select (counts->>'record_domains')::bigint from expected)
  union all
  select 'COUNT_SOURCES',
         (select count(*) from public.sources) =
         (select (counts->>'sources')::bigint from expected)
  union all
  select 'COUNT_SOURCE_LOCATIONS',
         (select count(*) from public.source_locations) =
         (select (counts->>'source_locations')::bigint from expected)
  union all
  select 'COUNT_RECORD_SOURCES',
         (select count(*) from public.record_sources) =
         (select (counts->>'record_sources')::bigint from expected)
  union all
  select 'COUNT_CASES',
         (select count(*) from public.cases) =
         (select (counts->>'cases')::bigint from expected)
  union all
  select 'COUNT_CASE_LINKS',
         (select count(*) from public.case_links) =
         (select (counts->>'case_links')::bigint from expected)
  union all
  select 'COUNT_ANALYTES',
         (select count(*) from public.analytes) =
         (select (counts->>'analytes')::bigint from expected)
  union all
  select 'COUNT_LABS',
         (select count(*) from public.labs) =
         (select (counts->>'labs')::bigint from expected)
  union all
  select 'COUNT_MEDICATIONS',
         (select count(*) from public.medications) =
         (select (counts->>'medications')::bigint from expected)
  union all
  select 'COUNT_MONITORING',
         (select count(*) from public.monitoring) =
         (select (counts->>'monitoring')::bigint from expected)
  union all
  select 'COUNT_PLAN_ITEMS',
         (select count(*) from public.plan_items) =
         (select (counts->>'plan_items')::bigint from expected)
  union all
  select 'COUNT_QUESTIONS',
         (select count(*) from public.questions) =
         (select (counts->>'questions')::bigint from expected)
  union all
  select 'COUNT_ID_RESERVATIONS',
         (select count(*) from public.id_reservations) =
         (select (counts->>'id_reservations')::bigint from expected)
),
structural_checks as (
  select 'SNAPSHOT_PRESENT' check_key,
         exists (
           select 1 from snapshot
           where value->>'status' = 'CAPTURED'
             and jsonb_typeof(value->'expected_counts') = 'object'
         ) pass
  union all
  select 'SNAPSHOT_FINGERPRINTS_PRESENT',
         exists (
           select 1 from snapshot
           where jsonb_typeof(value->'table_fingerprints') = 'object'
             and jsonb_object_length(value->'table_fingerprints') = 15
             and nullif(value->>'package_fingerprint','') is not null
         )
  union all
  select 'HISTORICAL_SOURCE_MANIFEST_PRESENT',
         exists (
           select 1 from snapshot
           where nullif(value->>'historical_sources_manifest_sha256','') is not null
         )
  union all
  select 'RECORD_ID_NNN_MATCH',
         not exists (
           select 1
           from public.records
           where nnn <> right(record_id,3)::integer
         )
  union all
  select 'ID_LEDGER_USED_EXACT',
         not exists (
           select 1
           from public.records r
           where not exists (
             select 1
             from public.id_reservations i
             where i.state='used'
               and i.record_id=r.record_id
               and i.nnn=r.nnn
           )
         )
         and not exists (
           select 1
           from public.id_reservations i
           where i.state='used'
             and not exists (
               select 1 from public.records r
               where r.record_id=i.record_id and r.nnn=i.nnn
             )
         )
  union all
  select 'NO_RESERVED_IDS_AT_FINAL_LOAD',
         not exists (
           select 1 from public.id_reservations where state='reserved'
         )
  union all
  select 'RECORD_TAGS_MATCH_RECORD_DOMAINS',
         not exists (
           select 1
           from public.records r
           where exists (
             (select unnest(r.tags))
             except
             (select rd.domain_code
              from public.record_domains rd
              where rd.record_id=r.record_id)
           )
           or exists (
             (select rd.domain_code
              from public.record_domains rd
              where rd.record_id=r.record_id)
             except
             (select unnest(r.tags))
           )
         )
  union all
  select 'RECORD_BODY_PRESENT',
         not exists (
           select 1 from public.records
           where nullif(btrim(body_text),'') is null
         )
  union all
  select 'SOURCE_BYTES_VERIFIED_SHAPE',
         not exists (
           select 1 from public.sources
           where size_bytes is null
              or sha256 is null
              or sha256 !~ '^[0-9a-fA-F]{64}$'
         )
  union all
  select 'SOURCE_PRIMARY_LOCATION_EXACT',
         not exists (
           select 1
           from public.sources s
           where 1 <> (
             select count(*)
             from public.source_locations l
             where l.source_id=s.source_id
               and l.location_role='PRIMARY'
               and l.verified_at is not null
           )
         )
  union all
  select 'LAB_LITERAL_PRESERVATION_MARKER',
         not exists (
           select 1 from public.labs
           where coalesce((metadata->>'literal_preserved')::boolean,false) is not true
         )
  union all
  select 'NO_REPRESENTATIVE_MVP_MARKERS',
         not exists (
           select 1 from (
             select metadata from public.records
             union all select metadata from public.domains
             union all select metadata from public.analytes
             union all select metadata from public.sources
             union all select metadata from public.cases
             union all select metadata from public.labs
             union all select metadata from public.medications
             union all select metadata from public.monitoring
             union all select metadata from public.plan_items
             union all select metadata from public.questions
           ) m
           where exists (
             select 1
             from jsonb_object_keys(m.metadata) k
             where k like 'mvp_%'
                or k = 'selection_role'
           )
         )
),
all_checks as (
  select * from count_checks
  union all
  select * from structural_checks
)
select
  check_key,
  case
    when check_key <> 'SNAPSHOT_PRESENT'
         and not exists (
           select 1 from snapshot
           where value->>'status'='CAPTURED'
         )
         and check_key like 'COUNT_%'
      then 'WAITING'
    when pass is true then 'PASS'
    when pass is false then 'FAIL'
    else 'WAITING'
  end as status
from all_checks
order by check_key;
