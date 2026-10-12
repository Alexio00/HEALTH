-- Owner-bound preservation exception; no registration API for ordinary roles.
CREATE TABLE health_writer.legacy_record_exceptions (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 record_id text NOT NULL UNIQUE,
 row_sha text NOT NULL CHECK(row_sha ~ '^[a-f0-9]{64}$'),
 baseline_set_sha text NOT NULL CHECK(baseline_set_sha ~ '^[a-f0-9]{64}$'),
 decision_sha text NOT NULL CHECK(decision_sha ~ '^[a-f0-9]{64}$'),
 owner_decision_ref text NOT NULL CHECK(length(owner_decision_ref) BETWEEN 8 AND 256),
 enabled boolean NOT NULL DEFAULT false
);
ALTER TABLE health_writer.legacy_record_exceptions ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION health_writer.records_schema_valid() RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $fn$
 SELECT NOT EXISTS(SELECT 1 FROM public.records r WHERE
  r.record_id !~ '^REC-[0-9]{8}-[0-9]{3}$' OR r.nnn NOT BETWEEN 1 AND 999
  OR (CASE WHEN right(r.record_id,3) ~ '^[0-9]{3}$' THEN right(r.record_id,3)::integer ELSE NULL END) IS DISTINCT FROM r.nnn
  OR nullif(btrim(r.title),'') IS NULL OR nullif(btrim(r.body_text),'') IS NULL
  OR nullif(btrim(r.provenance_status),'') IS NULL OR (r.status IS NOT NULL AND r.status NOT IN ('active','cancelled'))
  OR (substring(r.record_id,5,8)<>to_char(r.record_date,'YYYYMMDD') AND NOT EXISTS(
   SELECT 1 FROM health_writer.legacy_record_exceptions e
   WHERE e.enabled AND e.record_id=r.record_id AND e.row_sha=health_writer.sha(to_jsonb(r)))))
 AND NOT EXISTS(SELECT 1 FROM health_writer.legacy_record_exceptions e
  LEFT JOIN public.records r USING(record_id) WHERE e.enabled AND
   (r.record_id IS NULL OR e.row_sha IS DISTINCT FROM health_writer.sha(to_jsonb(r))
    OR substring(r.record_id,5,8)=to_char(r.record_date,'YYYYMMDD')));
$fn$;

CREATE FUNCTION health_writer.legacy_record_exception_report() RETURNS jsonb
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $fn$
 SELECT coalesce(jsonb_agg(jsonb_build_object('kind','UNCHANGED_LEGACY_ID_DATE',
  'row_sha',e.row_sha,'baseline_set_sha',e.baseline_set_sha,'decision_sha',e.decision_sha,
  'owner_decision_ref',e.owner_decision_ref,'unchanged',e.row_sha=health_writer.sha(to_jsonb(r)))), '[]'::jsonb)
 FROM health_writer.legacy_record_exceptions e JOIN public.records r USING(record_id) WHERE e.enabled;
$fn$;
REVOKE ALL ON TABLE health_writer.legacy_record_exceptions FROM PUBLIC,anon,authenticated,service_role,health_writer_executor,health_writer_authorizer,health_writer_verifier;
REVOKE ALL ON FUNCTION health_writer.records_schema_valid(),health_writer.legacy_record_exception_report() FROM PUBLIC,anon,authenticated,service_role,health_writer_executor,health_writer_authorizer,health_writer_verifier;
