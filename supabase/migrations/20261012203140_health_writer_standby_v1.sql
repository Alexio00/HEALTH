BEGIN;
SET LOCAL statement_timeout='30s';
CREATE ROLE health_writer_executor NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE health_writer_authorizer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE health_writer_verifier NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE SCHEMA health_writer;
COMMENT ON SCHEMA health_writer IS 'HEALTH_WRITER_STANDBY_V1';
REVOKE ALL ON SCHEMA health_writer FROM PUBLIC,anon,authenticated,service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA health_writer REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- TEST-only delta engine. Fixed schema rendered by build_fixture.py.
-- The approval/semantic-verifier input in this fixture is explicitly simulated.
-- This file does not deploy to public or authorize clinical operations.
CREATE TABLE health_writer.candidates (
 request_key text PRIMARY KEY, payload jsonb NOT NULL, candidate_sha text NOT NULL,
 approved boolean NOT NULL DEFAULT false, expires_at timestamptz NOT NULL,
 expected_before_sha text NOT NULL, expected_after_sha text NOT NULL
);
CREATE TABLE health_writer.semantic_receipts (
 request_key text REFERENCES health_writer.candidates(request_key), rule_id integer,
 candidate_sha text NOT NULL, after_sha text NOT NULL, evidence_sha text NOT NULL,
 status text NOT NULL, methodology text NOT NULL, checked_at timestamptz NOT NULL,
 PRIMARY KEY(request_key,rule_id)
);
CREATE TABLE health_writer.expected_labs (lab_id bigint PRIMARY KEY, literal_row jsonb NOT NULL);
CREATE TABLE health_writer.publish_audit (
 request_key text PRIMARY KEY, operation_id uuid NOT NULL, candidate_sha text NOT NULL, before_state jsonb NOT NULL,
 after_state jsonb NOT NULL, before_sha text NOT NULL, after_sha text NOT NULL
);
CREATE FUNCTION health_writer.checkpoint() RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE t text; result jsonb='{}'; rows jsonb;
BEGIN
 FOREACH t IN ARRAY ARRAY['records','domains','record_domains','sources','source_locations','record_sources','cases','case_links','analytes','labs','medications','monitoring','plan_items','questions','id_reservations'] LOOP
  EXECUTE format('SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),''[]''::jsonb) FROM public.%I x',t) INTO rows;
  result:=result||jsonb_build_object(t,rows);
 END LOOP;
 RETURN result;
END $fn$;
CREATE FUNCTION health_writer.sha(value jsonb) RETURNS text LANGUAGE sql IMMUTABLE
SET search_path=pg_catalog,pg_temp AS $fn$ SELECT encode(sha256(convert_to(value::text,'UTF8')),'hex') $fn$;

CREATE FUNCTION health_writer.apply_delta_internal(changes jsonb, p_operation uuid) RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE delta jsonb; t text; action text; keys text[]; k text; col text; cols text=''; sets text=''; predicate text; current_row jsonb; data jsonb; n bigint;
BEGIN
 IF jsonb_typeof(changes) IS DISTINCT FROM 'array' OR jsonb_array_length(changes)>100 THEN RAISE EXCEPTION 'invalid changes'; END IF;
 FOR delta IN SELECT jsonb_array_elements(changes) LOOP
  IF (SELECT count(*) FROM jsonb_object_keys(delta) x WHERE x NOT IN ('table','action','key','expected_sha','row'))>0 THEN RAISE EXCEPTION 'unknown delta field'; END IF;
  t:=delta->>'table'; action:=delta->>'action'; data:=delta->'row';
  keys:=CASE t
   WHEN 'records' THEN ARRAY['record_id'] WHEN 'cases' THEN ARRAY['case_key']
   WHEN 'case_links' THEN ARRAY['case_key','record_id','relation']
   WHEN 'labs' THEN ARRAY['lab_id'] WHEN 'medications' THEN ARRAY['medication_id']
   WHEN 'monitoring' THEN ARRAY['monitoring_id'] WHEN 'plan_items' THEN ARRAY['plan_item_id']
   WHEN 'questions' THEN ARRAY['question_id'] WHEN 'record_domains' THEN ARRAY['record_id','domain_code']
   WHEN 'record_sources' THEN ARRAY['record_id','source_id','role']
   WHEN 'sources' THEN ARRAY['source_id']
   WHEN 'source_locations' THEN ARRAY['source_id','provider','account_alias','provider_object_id','location_role']
   ELSE NULL END;
  IF keys IS NULL OR action IS NULL OR action NOT IN ('INSERT','UPDATE','DELETE') THEN RAISE EXCEPTION 'unsupported table/action'; END IF;
  IF t IN ('sources','source_locations') THEN
   IF action IS DISTINCT FROM 'INSERT' THEN RAISE EXCEPTION 'unsupported table/action'; END IF;
   IF p_operation IS NULL
    OR to_regclass('health_writer.source_uploads') IS NULL THEN
    RAISE EXCEPTION 'Source creation requires durable upload protocol'; END IF;
   IF NOT EXISTS(SELECT 1 FROM health_writer.source_uploads u WHERE u.operation_id=p_operation
     AND u.source_id=data->>'source_id' AND u.state IN ('PLANNED','UNCERTAIN','VERIFIED')
     AND CASE WHEN t='sources' THEN u.source_row=data ELSE
       u.provider=data->>'provider' AND u.account_alias=data->>'account_alias'
       AND data->>'location_role'='PRIMARY' AND data->>'verified_at' IS NOT NULL END)
    THEN RAISE EXCEPTION 'Source upload binding missing'; END IF;
  END IF;
  IF t='records' AND action='DELETE' THEN RAISE EXCEPTION 'REC allocation/purge requires separate protocol'; END IF;
  IF t='records' AND action='INSERT' AND (p_operation IS NULL OR NOT EXISTS(
   SELECT 1 FROM public.id_reservations r WHERE r.operation_id=p_operation
    AND r.state='reserved' AND r.nnn=(data->>'nnn')::integer
    AND r.metadata->>'proposed_record_id'=data->>'record_id'
    AND r.metadata->>'record_date'=data->>'record_date'
  )) THEN RAISE EXCEPTION 'REC allocation/purge requires separate protocol'; END IF;
  IF jsonb_typeof(delta->'key') IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(delta->'key'))<>cardinality(keys) THEN RAISE EXCEPTION 'exact key required'; END IF;
  predicate:='';
  FOREACH k IN ARRAY keys LOOP
   IF nullif(delta->'key'->>k,'') IS NULL THEN RAISE EXCEPTION 'missing key'; END IF;
   predicate:=predicate||CASE WHEN predicate='' THEN '' ELSE ' AND ' END||format('to_jsonb(x)->%L = $1->%L',k,k);
  END LOOP;
  EXECUTE format('SELECT to_jsonb(x) FROM public.%I x WHERE %s FOR UPDATE',t,predicate) USING delta->'key' INTO current_row;
  IF action='INSERT' THEN
   IF current_row IS NOT NULL OR delta->>'expected_sha' IS NOT NULL THEN RAISE EXCEPTION 'insert conflict'; END IF;
  ELSE
   IF current_row IS NULL OR health_writer.sha(current_row) IS DISTINCT FROM delta->>'expected_sha' THEN RAISE EXCEPTION 'stale or missing row'; END IF;
  END IF;
  IF action='DELETE' THEN
   EXECUTE format('DELETE FROM public.%I x WHERE %s',t,predicate) USING delta->'key';
  ELSE
   IF jsonb_typeof(data) IS DISTINCT FROM 'object' OR data='{}'::jsonb THEN RAISE EXCEPTION 'row fields required'; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_object_keys(data) c WHERE NOT EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('public.'||t) AND a.attname=c AND a.attnum>0 AND NOT a.attisdropped)) THEN RAISE EXCEPTION 'unknown column'; END IF;
   FOREACH k IN ARRAY keys LOOP
    IF action='INSERT' AND data->k IS DISTINCT FROM delta->'key'->k THEN RAISE EXCEPTION 'insert key mismatch'; END IF;
    IF action='UPDATE' AND data ? k THEN RAISE EXCEPTION 'immutable key'; END IF;
   END LOOP;
   IF t='records' AND action='UPDATE' AND (data ? 'nnn' OR data ? 'record_date' OR data ? 'created_at') THEN RAISE EXCEPTION 'immutable REC identity'; END IF;
   cols:=''; sets:='';
   FOR col IN SELECT jsonb_object_keys(data) ORDER BY 1 LOOP
    cols:=cols||CASE WHEN cols='' THEN '' ELSE ',' END||quote_ident(col);
    sets:=sets||CASE WHEN sets='' THEN '' ELSE ',' END||format('%I=v.%I',col,col);
   END LOOP;
   IF action='INSERT' THEN
    EXECUTE format('INSERT INTO public.%I (%s) OVERRIDING SYSTEM VALUE SELECT %s FROM jsonb_populate_record(NULL::public.%I,$1) v',t,cols,cols,t) USING data;
   ELSE
    EXECUTE format('UPDATE public.%I x SET %s FROM jsonb_populate_record(NULL::public.%I,$2) v WHERE %s',t,sets,t,predicate) USING delta->'key',data;
   END IF;
  END IF;
  GET DIAGNOSTICS n=ROW_COUNT;
  IF n<>1 THEN RAISE EXCEPTION 'affected row count mismatch'; END IF;
 END LOOP;
END $fn$;

CREATE FUNCTION health_writer.apply_delta(changes jsonb) RETURNS void
LANGUAGE sql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $fn$
 SELECT health_writer.apply_delta_internal(changes,NULL);
$fn$;

CREATE FUNCTION health_writer.publish_internal(p_key text, p_operation uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE c health_writer.candidates%rowtype; before_state jsonb; after_state jsonb; op uuid; v_sha text;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'candidate missing'; END IF;
 IF EXISTS(SELECT 1 FROM health_writer.publish_audit WHERE request_key=p_key) THEN
  IF c.candidate_sha IS DISTINCT FROM health_writer.sha(c.payload) OR c.candidate_sha IS DISTINCT FROM (SELECT a.candidate_sha FROM health_writer.publish_audit a WHERE a.request_key=p_key) THEN RAISE EXCEPTION 'idempotency payload conflict'; END IF;
  RETURN jsonb_build_object('state','FINALIZED','replayed',true,'protocol','HEALTH_WRITER_V1');
 END IF;
 IF c.approved IS NOT TRUE OR c.expires_at<=clock_timestamp() OR c.candidate_sha IS DISTINCT FROM health_writer.sha(c.payload) THEN RAISE EXCEPTION 'approval missing/expired/tampered'; END IF;
 -- Lock the fixture domain so non-protocol fixture writes cannot race this checkpoint.
 LOCK TABLE public.records,public.domains,public.record_domains,public.sources,public.source_locations,public.record_sources,public.cases,public.case_links,public.analytes,public.labs,public.medications,public.monitoring,public.plan_items,public.questions,public.id_reservations IN SHARE ROW EXCLUSIVE MODE;
 before_state:=health_writer.checkpoint();
 IF health_writer.sha(before_state) IS DISTINCT FROM c.expected_before_sha THEN RAISE EXCEPTION 'stale domain snapshot'; END IF;
 IF p_operation IS NULL THEN
  INSERT INTO public.operations(operation,mode,scope,state,notes) VALUES('HEALTH_WRITER_LEGACY_DISABLED','maintenance',ARRAY[p_key],'PREPARED','synthetic approval/verifier only') RETURNING operation_id INTO op;
 ELSE
  SELECT operation_id INTO op FROM public.operations
   WHERE operation_id=p_operation AND operation='HEALTH_WRITER_DELTA_V1'
    AND state='PREPARED' AND scope=ARRAY[p_key] FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'foreign operation or operation class'; END IF;
 END IF;
 UPDATE public.operations SET state='COMMITTED_REGISTRY',updated_at=clock_timestamp() WHERE operation_id=op;
 PERFORM health_writer.apply_delta_internal(c.payload->'changes',p_operation);
 IF p_operation IS NOT NULL THEN
  IF EXISTS(SELECT 1 FROM public.id_reservations r WHERE r.operation_id=op AND r.state='reserved'
   AND NOT EXISTS(SELECT 1 FROM public.records x WHERE x.nnn=r.nnn AND x.record_id=r.metadata->>'proposed_record_id'))
   THEN RAISE EXCEPTION 'reserved REC not materialized'; END IF;
  IF EXISTS(SELECT 1 FROM public.id_reservations WHERE operation_id=op AND state='reserved')
   AND ((c.payload->>'ledger_updated_at')::timestamptz IS NULL
    OR (c.payload->>'ledger_updated_at')::timestamptz>clock_timestamp()
    OR (c.payload->>'ledger_updated_at')::timestamptz<clock_timestamp()-interval '10 minutes')
   THEN RAISE EXCEPTION 'ledger transition timestamp missing/stale'; END IF;
  UPDATE public.id_reservations SET state='used',record_id=metadata->>'proposed_record_id',updated_at=(c.payload->>'ledger_updated_at')::timestamptz
   WHERE operation_id=op AND state='reserved';
 END IF;
 after_state:=health_writer.checkpoint();v_sha:=health_writer.sha(after_state);
 PERFORM health_writer.validate_lab_delta(p_key,before_state,after_state);
 IF v_sha IS DISTINCT FROM c.expected_after_sha THEN RAISE EXCEPTION 'unexpected after snapshot'; END IF;
 IF (SELECT count(*) FROM health_writer.structural_checks())<>20 OR EXISTS(SELECT 1 FROM health_writer.structural_checks() WHERE passed IS DISTINCT FROM true) THEN RAISE EXCEPTION 'structural validation failed'; END IF;
 IF EXISTS(SELECT 1 FROM public.record_domains d LEFT JOIN public.records r ON r.record_id=d.record_id WHERE r.record_id IS NULL) OR EXISTS(SELECT 1 FROM public.records r WHERE ARRAY(SELECT d.domain_code FROM public.record_domains d WHERE d.record_id=r.record_id ORDER BY 1) IS DISTINCT FROM ARRAY(SELECT DISTINCT unnest(r.tags) ORDER BY 1)) THEN RAISE EXCEPTION 'domain representation mismatch'; END IF;
 IF EXISTS(SELECT 1 FROM public.record_sources r LEFT JOIN public.records x ON x.record_id=r.record_id LEFT JOIN public.sources s ON s.source_id=r.source_id WHERE x.record_id IS NULL OR s.source_id IS NULL) OR EXISTS(SELECT 1 FROM public.sources s WHERE s.sha256 IS NULL OR s.sha256 !~ '^[a-fA-F0-9]{64}$' OR s.size_bytes IS NULL OR s.size_bytes<0 OR (SELECT count(*) FROM public.source_locations l WHERE l.source_id=s.source_id AND l.location_role='PRIMARY' AND l.verified_at IS NOT NULL)<>1) THEN RAISE EXCEPTION 'source binding invalid'; END IF;
 IF EXISTS(SELECT 1 FROM (SELECT basis_record_id FROM public.medications UNION ALL SELECT basis_record_id FROM public.monitoring UNION ALL SELECT basis_record_id FROM public.plan_items UNION ALL SELECT basis_record_id FROM public.questions) d WHERE d.basis_record_id IS NULL OR NOT EXISTS(SELECT 1 FROM public.records r WHERE r.record_id=d.basis_record_id)) THEN RAISE EXCEPTION 'derived basis missing'; END IF;
 IF EXISTS(SELECT 1 FROM public.medications m WHERE m.status='active' AND (NOT EXISTS(SELECT 1 FROM jsonb_array_elements(before_state->'medications') old WHERE old=to_jsonb(m)) OR (m.metadata->>'intake_event' IS NOT NULL AND EXISTS(SELECT 1 FROM jsonb_array_elements(before_state->'questions') old WHERE old->'basis_record_id'=to_jsonb(m.basis_record_id) AND old->'metadata'->>'medication_id'=m.medication_id::text AND old->'metadata'->>'intake_event'=m.metadata->>'intake_event' AND NOT EXISTS(SELECT 1 FROM public.questions q WHERE to_jsonb(q)=old)))) AND (m.metadata->>'intake_event' IS NULL OR (SELECT count(*) FROM public.questions q WHERE q.status='open' AND q.basis_record_id=m.basis_record_id AND q.metadata->>'medication_id'=m.medication_id::text AND q.metadata->>'intake_event'=m.metadata->>'intake_event' AND q.metadata->>'check_kind'='drug_interactions')<>1)) THEN RAISE EXCEPTION 'interaction question missing or duplicated'; END IF;
 IF (SELECT count(*) FROM health_writer.semantic_receipts s WHERE s.request_key=p_key AND s.rule_id IN (19,20,21,22,27,28,29,30,31,37) AND s.status='PASS' AND s.candidate_sha=c.candidate_sha AND s.after_sha=v_sha AND s.checked_at>clock_timestamp()-interval '10 minutes' AND s.checked_at<=clock_timestamp() AND s.evidence_sha~'^[a-f0-9]{64}$' AND nullif(s.methodology,'') IS NOT NULL)<>10 THEN RAISE EXCEPTION 'semantic/source evidence missing or stale'; END IF;
 IF c.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'approval expired during publication'; END IF;
 INSERT INTO health_writer.publish_audit VALUES(p_key,op,c.candidate_sha,before_state,after_state,c.expected_before_sha,v_sha);
 UPDATE public.operations SET state='VALIDATED',updated_at=clock_timestamp() WHERE operation_id=op;
 UPDATE public.operations SET state='FINALIZED',result='success',finalized_at=clock_timestamp(),updated_at=clock_timestamp() WHERE operation_id=op;
 RETURN jsonb_build_object('state','FINALIZED','replayed',false,'protocol','HEALTH_WRITER_V1');
END $fn$;

CREATE FUNCTION health_writer.publish(p_key text) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
 SELECT health_writer.publish_internal(p_key,NULL);
$fn$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA health_writer FROM PUBLIC;

-- TEST-only recovery lookup after an uncertain client acknowledgement.
-- Return operation metadata only; keep clinical snapshots administrator-only.
CREATE FUNCTION health_writer.status(p_key text) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
 SELECT CASE WHEN a.request_key IS NOT NULL
  THEN jsonb_build_object('state','FINALIZED','operation_id',a.operation_id,
      'candidate_sha',a.candidate_sha,'after_sha',a.after_sha,'protocol','HEALTH_WRITER_V1')
  WHEN c.request_key IS NOT NULL
  THEN jsonb_build_object('state','CANDIDATE','candidate_sha',c.candidate_sha,'protocol','HEALTH_WRITER_V1')
  ELSE jsonb_build_object('state','NOT_FOUND','protocol','HEALTH_WRITER_V1') END
 FROM (SELECT p_key request_key) k
 LEFT JOIN health_writer.candidates c USING(request_key)
 LEFT JOIN health_writer.publish_audit a USING(request_key)
$fn$;
REVOKE ALL ON FUNCTION health_writer.status(text) FROM PUBLIC;

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

CREATE FUNCTION health_writer.lab_check_context_valid() RETURNS boolean LANGUAGE sql STABLE SET search_path=pg_catalog,pg_temp AS 'SELECT false';
-- Prototype: render health_writer only to a fresh health_writer_fixture_* schema.
-- SECURITY INVOKER. Does not mint semantic PASS or authorize publication.
CREATE FUNCTION health_writer.structural_checks()
RETURNS TABLE(rule_id integer, passed boolean)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog, pg_temp
AS $checks$
SELECT 1, NOT EXISTS(SELECT record_id FROM public.records GROUP BY record_id HAVING count(*)<>1)
UNION ALL SELECT 2, NOT EXISTS(SELECT 1 FROM public.record_domains d LEFT JOIN public.domains k ON k.domain_code=d.domain_code LEFT JOIN public.records r ON r.record_id=d.record_id WHERE k.domain_code IS NULL OR r.record_id IS NULL OR NOT k.active)
UNION ALL SELECT 3, NOT EXISTS(SELECT 1 FROM public.cases c LEFT JOIN public.records r ON r.record_id=c.case_key WHERE r.record_id IS NULL)
UNION ALL SELECT 4, NOT EXISTS(SELECT 1 FROM public.case_links l LEFT JOIN public.cases c ON c.case_key=l.case_key LEFT JOIN public.records r ON r.record_id=l.record_id WHERE c.case_key IS NULL OR r.record_id IS NULL OR l.relation NOT IN ('OPEN','CONTINUES','CLOSES','FOLLOWUP')) AND NOT EXISTS(SELECT 1 FROM public.cases c WHERE (SELECT count(*) FROM public.case_links l WHERE l.case_key=c.case_key AND l.relation='OPEN' AND l.record_id=c.opening_record_id)<>1)
UNION ALL SELECT 5, NOT EXISTS(SELECT 1 FROM public.cases c LEFT JOIN public.records r ON r.record_id=c.closing_record_id WHERE c.status='closed' AND r.record_id IS NULL)
UNION ALL SELECT 6, NOT EXISTS(SELECT 1 FROM public.labs l LEFT JOIN public.records r ON r.record_id=l.record_id WHERE r.record_id IS NULL)
UNION ALL SELECT 7, NOT EXISTS(SELECT 1 FROM public.labs l LEFT JOIN public.analytes a ON a.analyte_key=l.analyte_key WHERE a.analyte_key IS NULL)
UNION ALL SELECT 8, NOT EXISTS(SELECT 1 FROM public.records r WHERE (SELECT count(*) FROM public.id_reservations i WHERE i.record_id=r.record_id AND i.nnn=r.nnn AND i.state='used')<>1) AND NOT EXISTS(SELECT nnn FROM public.records GROUP BY nnn HAVING count(*)>1)
UNION ALL SELECT 11, health_writer.records_schema_valid()
UNION ALL SELECT 14, NOT EXISTS(SELECT 1 FROM public.operations WHERE mode NOT IN ('import','maintenance') OR state NOT IN ('PREPARED','COMMITTED_REGISTRY','VALIDATED','FINALIZED','FAILED') OR cardinality(scope)=0 OR (state='FINALIZED' AND (result IS NULL OR finalized_at IS NULL)))
-- Literal lab validation is request-scoped, performed before this check.
UNION ALL SELECT 18, health_writer.lab_check_context_valid()
UNION ALL SELECT 23, (SELECT count(*) FROM public.operations WHERE state IN ('PREPARED','COMMITTED_REGISTRY','VALIDATED'))<=1
UNION ALL SELECT 24, NOT EXISTS(SELECT 1 FROM health_writer.semantic_receipts s WHERE s.status<>'PASS' OR s.checked_at IS NULL OR s.candidate_sha !~ '^[a-f0-9]{64}$' OR s.after_sha !~ '^[a-f0-9]{64}$' OR s.evidence_sha !~ '^[a-f0-9]{64}$' OR nullif(s.methodology,'') IS NULL)
UNION ALL SELECT 25, NOT EXISTS(SELECT analyte_key FROM public.analytes GROUP BY analyte_key HAVING count(*)<>1)
UNION ALL SELECT 26, NOT EXISTS(SELECT 1 FROM public.labs GROUP BY record_id,observed_on,analyte_key,value,unit,reference_range,flag,source_name,note HAVING count(*)>1)
UNION ALL SELECT 32, NOT EXISTS(SELECT 1 FROM public.id_reservations i WHERE (i.state='used' AND NOT EXISTS(SELECT 1 FROM public.records r WHERE r.record_id=i.record_id AND r.nnn=i.nnn)) OR (i.state IN ('reserved','retired') AND i.record_id IS NOT NULL) OR i.state NOT IN ('used','retired','reserved')) AND NOT EXISTS(SELECT nnn FROM public.id_reservations GROUP BY nnn HAVING count(*)>1) AND NOT EXISTS(SELECT record_id FROM public.id_reservations WHERE record_id IS NOT NULL GROUP BY record_id HAVING count(*)>1)
UNION ALL SELECT 33, NOT EXISTS(SELECT 1 FROM public.cases WHERE case_key<>opening_record_id)
UNION ALL SELECT 34, NOT EXISTS(SELECT 1 FROM public.cases c WHERE c.status NOT IN ('open','closed') OR (c.status='open' AND (c.closing_record_id IS NOT NULL OR EXISTS(SELECT 1 FROM public.case_links l WHERE l.case_key=c.case_key AND l.relation='CLOSES'))) OR (c.status='closed' AND (c.closing_record_id IS NULL OR (SELECT count(*) FROM public.case_links l WHERE l.case_key=c.case_key AND l.relation='CLOSES')<>1 OR NOT EXISTS(SELECT 1 FROM public.case_links l WHERE l.case_key=c.case_key AND l.relation='CLOSES' AND l.record_id=c.closing_record_id))))
UNION ALL SELECT 35, NOT EXISTS(SELECT 1 FROM public.case_links GROUP BY case_key,record_id,relation HAVING count(*)>1)
UNION ALL SELECT 36, NOT EXISTS(SELECT 1 FROM health_writer.semantic_receipts s LEFT JOIN health_writer.candidates c ON c.request_key=s.request_key WHERE c.request_key IS NULL);
$checks$;
REVOKE ALL ON FUNCTION health_writer.structural_checks() FROM PUBLIC;

-- Optional TEST-only overlay. No production migration, Auth or owner verifier.
-- Trusted administrator provisions intents and exact candidate approvals.
CREATE TABLE health_writer.writer_intents (
 request_key text PRIMARY KEY, caller name NOT NULL, intent jsonb NOT NULL,
 intent_sha text NOT NULL CHECK(intent_sha ~ '^[a-f0-9]{64}$'),
 approved boolean NOT NULL DEFAULT false, expires_at timestamptz NOT NULL
);
CREATE TABLE health_writer.prepared_requests (
 request_key text PRIMARY KEY REFERENCES health_writer.writer_intents(request_key),
 operation_id uuid UNIQUE NOT NULL REFERENCES public.operations(operation_id),
 caller name NOT NULL, intent_sha text NOT NULL,
 operation_class text NOT NULL CHECK(operation_class='HEALTH_WRITER_DELTA_V1'),
 proposed_record_id text, nnn integer, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE health_writer.writer_validation_results (
 operation_id uuid REFERENCES public.operations(operation_id), rule_id integer,
 status text NOT NULL CHECK(status='PASS'), candidate_sha text NOT NULL,
 after_sha text NOT NULL, checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(operation_id,rule_id)
);
ALTER TABLE health_writer.writer_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.prepared_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.writer_validation_results ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION health_writer.prepare(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE i health_writer.writer_intents%rowtype; p health_writer.prepared_requests%rowtype;
 op uuid; number integer; rec text; day date;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO i FROM health_writer.writer_intents WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR i.caller IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 IF i.intent_sha IS DISTINCT FROM health_writer.sha(i.intent) THEN RAISE EXCEPTION 'intent digest conflict'; END IF;
 SELECT * INTO p FROM health_writer.prepared_requests WHERE request_key=p_key;
 IF FOUND THEN
  IF p.intent_sha IS DISTINCT FROM i.intent_sha OR p.caller IS DISTINCT FROM session_user THEN RAISE EXCEPTION 'prepared request conflict'; END IF;
  RETURN health_writer.request_status(p_key);
 END IF;
 IF i.approved IS NOT TRUE OR i.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'intent approval missing/expired'; END IF;
 IF jsonb_typeof(i.intent) IS DISTINCT FROM 'object'
  OR i.intent->>'action' IS NULL OR i.intent->>'action' NOT IN ('CREATE_REC','UPDATE')
  OR EXISTS(SELECT 1 FROM jsonb_object_keys(i.intent) k WHERE k NOT IN ('action','record_date','user_message_sha256','conversation_ref'))
  THEN RAISE EXCEPTION 'invalid intent'; END IF;
 INSERT INTO public.operations(operation,mode,scope,state,notes)
  VALUES('HEALTH_WRITER_DELTA_V1','maintenance',ARRAY[p_key],'PREPARED','owner-bound routine Writer operation') RETURNING operation_id INTO op;
 IF i.intent->>'action'='CREATE_REC' THEN
  day:=(i.intent->>'record_date')::date;
  IF day IS NULL OR day::text IS DISTINCT FROM i.intent->>'record_date' THEN RAISE EXCEPTION 'exact record date required'; END IF;
  SELECT coalesce(max(n),0)+1 INTO number FROM (
   SELECT nnn n FROM public.id_reservations UNION ALL SELECT nnn FROM public.records) x;
  IF number>999 THEN RAISE EXCEPTION 'NNN exhausted'; END IF;
  rec:='REC-'||to_char(day,'YYYYMMDD')||'-'||lpad(number::text,3,'0');
  INSERT INTO public.id_reservations(nnn,state,operation_id,reserved_at,metadata)
   VALUES(number,'reserved',op,clock_timestamp(),jsonb_build_object('proposed_record_id',rec,'record_date',day::text));
 END IF;
 INSERT INTO health_writer.prepared_requests VALUES(p_key,op,session_user,i.intent_sha,'HEALTH_WRITER_DELTA_V1',rec,number,clock_timestamp());
 RETURN health_writer.request_status(p_key);
END $fn$;

CREATE FUNCTION health_writer.request_status(p_key text) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p health_writer.prepared_requests%rowtype; state text; digest text;
BEGIN
 SELECT * INTO p FROM health_writer.prepared_requests WHERE request_key=p_key;
 IF NOT FOUND THEN
  IF NOT EXISTS(SELECT 1 FROM health_writer.writer_intents WHERE request_key=p_key AND caller=session_user)
   THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
  RETURN jsonb_build_object('state','NOT_PREPARED','protocol','HEALTH_WRITER_V1');
 END IF;
 IF p.caller IS DISTINCT FROM session_user THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT o.state INTO state FROM public.operations o WHERE operation_id=p.operation_id;
 SELECT candidate_sha INTO digest FROM health_writer.publish_audit WHERE request_key=p_key;
 RETURN jsonb_build_object('state',state,'operation_id',p.operation_id,'record_id',p.proposed_record_id,'nnn',p.nnn,'candidate_sha',digest,'protocol','HEALTH_WRITER_V1');
END $fn$;

CREATE FUNCTION health_writer.finalize(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p health_writer.prepared_requests%rowtype; i health_writer.writer_intents%rowtype;
 c health_writer.candidates%rowtype; result jsonb; a health_writer.publish_audit%rowtype;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO p FROM health_writer.prepared_requests WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR p.caller IS DISTINCT FROM session_user THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT * INTO i FROM health_writer.writer_intents WHERE request_key=p_key FOR UPDATE;
 SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key FOR UPDATE;
 IF p.operation_class<>'HEALTH_WRITER_DELTA_V1' OR i.caller IS DISTINCT FROM p.caller
  OR i.intent_sha IS DISTINCT FROM p.intent_sha OR i.intent_sha IS DISTINCT FROM health_writer.sha(i.intent)
  THEN RAISE EXCEPTION 'prepared request binding conflict'; END IF;
 IF EXISTS(SELECT 1 FROM health_writer.publish_audit WHERE request_key=p_key) THEN
  SELECT * INTO a FROM health_writer.publish_audit WHERE request_key=p_key;
  IF a.operation_id IS DISTINCT FROM p.operation_id THEN RAISE EXCEPTION 'audit operation conflict'; END IF;
  RETURN health_writer.publish_internal(p_key,p.operation_id);
 END IF;
 IF i.approved IS NOT TRUE OR i.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'intent approval missing/expired'; END IF;
 IF c.payload->>'intent_sha' IS DISTINCT FROM p.intent_sha THEN RAISE EXCEPTION 'candidate intent binding missing'; END IF;
 IF p.nnn IS NULL AND EXISTS(SELECT 1 FROM jsonb_array_elements(c.payload->'changes') d WHERE d->>'table'='records' AND d->>'action'='INSERT')
  THEN RAISE EXCEPTION 'unexpected REC allocation'; END IF;
 result:=health_writer.publish_internal(p_key,p.operation_id);
 IF i.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'intent approval expired during publication'; END IF;
 SELECT * INTO a FROM health_writer.publish_audit WHERE request_key=p_key;
 INSERT INTO health_writer.writer_validation_results
  SELECT p.operation_id,rule_id,'PASS',a.candidate_sha,a.after_sha,clock_timestamp() FROM health_writer.structural_checks()
  UNION ALL
  SELECT p.operation_id,rule_id,'PASS',a.candidate_sha,a.after_sha,clock_timestamp()
   FROM health_writer.semantic_receipts WHERE request_key=p_key AND rule_id IN (19,20,21,22,27,28,29,30,31,37);
 RETURN result;
END $fn$;

CREATE FUNCTION health_writer.abandon(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p health_writer.prepared_requests%rowtype; op_state text;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO p FROM health_writer.prepared_requests WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR p.caller IS DISTINCT FROM session_user THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT o.state INTO op_state FROM public.operations o WHERE operation_id=p.operation_id
  AND operation='HEALTH_WRITER_DELTA_V1' AND scope=ARRAY[p_key] FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'foreign operation or operation class'; END IF;
 IF op_state='FAILED' THEN RETURN health_writer.request_status(p_key); END IF;
 IF op_state IS DISTINCT FROM 'PREPARED' OR EXISTS(SELECT 1 FROM health_writer.publish_audit WHERE request_key=p_key)
  THEN RAISE EXCEPTION 'published or uncertain operation cannot be abandoned'; END IF;
 UPDATE public.id_reservations SET state='retired',updated_at=clock_timestamp() WHERE operation_id=p.operation_id AND state='reserved';
 UPDATE public.operations SET state='FAILED',result='abandoned',updated_at=clock_timestamp() WHERE operation_id=p.operation_id;
 RETURN health_writer.request_status(p_key);
END $fn$;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA health_writer FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION health_writer.publish(text),health_writer.status(text) FROM health_writer_executor;
GRANT EXECUTE ON FUNCTION health_writer.prepare(text),health_writer.finalize(text),health_writer.request_status(text),health_writer.abandon(text) TO health_writer_executor;

-- Optional disposable TEST integration; install after durable_runtime.sql.
-- Separate verifier login attests actual adapter bytes. No production deployment.
CREATE TABLE health_writer.source_verifier_principals (principal name PRIMARY KEY);
CREATE TABLE health_writer.source_uploads (
 request_key text REFERENCES health_writer.prepared_requests(request_key),
 operation_id uuid NOT NULL REFERENCES public.operations(operation_id),
 source_id text NOT NULL UNIQUE, marker uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
 source_row jsonb NOT NULL, provider text NOT NULL, account_alias text NOT NULL,
 state text NOT NULL DEFAULT 'PLANNED' CHECK(state IN ('PLANNED','UNCERTAIN','VERIFIED','BLOCKED','PUBLISHED')),
 object_id text, candidate_sha text, verifier name, checked_at timestamptz, safe_error text,
 PRIMARY KEY(request_key,source_id)
);
ALTER TABLE health_writer.source_verifier_principals ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.source_uploads ENABLE ROW LEVEL SECURITY;
CREATE UNIQUE INDEX source_upload_logical_path_unique ON health_writer.source_uploads ((source_row->>'logical_path'));

CREATE FUNCTION health_writer.plan_source(p_key text,p_source jsonb,p_provider text,p_account text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p health_writer.prepared_requests%rowtype; u health_writer.source_uploads%rowtype;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO p FROM health_writer.prepared_requests WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR p.caller IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 IF (SELECT state FROM public.operations WHERE operation_id=p.operation_id) IS DISTINCT FROM 'PREPARED'
  THEN RAISE EXCEPTION 'operation not prepared'; END IF;
 IF jsonb_typeof(p_source) IS DISTINCT FROM 'object'
  OR p_source->>'source_id' IS NULL OR (p_source->>'source_id') !~ '^SRC-[0-9]{8}-[0-9]{3,}$'
  OR p_source->>'sha256' IS NULL OR (p_source->>'sha256') !~ '^[a-f0-9]{64}$'
  OR jsonb_typeof(p_source->'size_bytes') IS DISTINCT FROM 'number'
  OR (p_source->>'size_bytes') !~ '^[0-9]+$'
  OR nullif(p_source->>'logical_path','') IS NULL OR nullif(p_source->>'original_filename','') IS NULL
  OR p_provider IS NULL OR p_provider NOT IN ('LOCAL_TEST','google-drive')
  OR p_account IS NULL OR p_account IS DISTINCT FROM 'HEALTH_PRIMARY'
  OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_source) k WHERE k NOT IN
    ('source_id','logical_path','original_filename','mime_type','size_bytes','sha256','source_date','metadata','created_at'))
  THEN RAISE EXCEPTION 'invalid Source plan'; END IF;
 PERFORM (p_source->>'size_bytes')::bigint;
 SELECT * INTO u FROM health_writer.source_uploads WHERE request_key=p_key AND source_id=p_source->>'source_id';
 IF FOUND THEN
  IF u.source_row IS DISTINCT FROM p_source OR u.provider IS DISTINCT FROM p_provider OR u.account_alias IS DISTINCT FROM p_account
   OR u.operation_id IS DISTINCT FROM p.operation_id THEN RAISE EXCEPTION 'Source plan replay conflict'; END IF;
 ELSE
  IF EXISTS(SELECT 1 FROM public.sources WHERE source_id=p_source->>'source_id' OR logical_path=p_source->>'logical_path')
   THEN RAISE EXCEPTION 'existing Source identity/path'; END IF;
  INSERT INTO health_writer.source_uploads(request_key,operation_id,source_id,source_row,provider,account_alias)
   VALUES(p_key,p.operation_id,p_source->>'source_id',p_source,p_provider,p_account);
 END IF;
 RETURN health_writer.source_status(p_key,p_source->>'source_id');
END $fn$;

CREATE FUNCTION health_writer.source_status(p_key text,p_source text) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u health_writer.source_uploads%rowtype;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM health_writer.prepared_requests WHERE request_key=p_key AND caller=session_user)
  THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT * INTO u FROM health_writer.source_uploads WHERE request_key=p_key AND source_id=p_source;
 IF NOT FOUND THEN RAISE EXCEPTION 'Source plan missing'; END IF;
 RETURN jsonb_build_object('operation_id',u.operation_id,'source_id',u.source_id,'marker',u.marker,
  'state',u.state,'object_id',u.object_id,'candidate_sha',u.candidate_sha,'safe_error',u.safe_error,'protocol','HEALTH_WRITER_V1');
END $fn$;

CREATE FUNCTION health_writer.source_uncertain(p_key text,p_source text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 PERFORM health_writer.source_status(p_key,p_source);
 IF (SELECT o.state FROM public.operations o JOIN health_writer.prepared_requests p USING(operation_id)
  WHERE p.request_key=p_key) IS DISTINCT FROM 'PREPARED' THEN RAISE EXCEPTION 'operation not prepared'; END IF;
 UPDATE health_writer.source_uploads SET state='UNCERTAIN' WHERE request_key=p_key AND source_id=p_source AND state='PLANNED';
 IF (SELECT state FROM health_writer.source_uploads WHERE request_key=p_key AND source_id=p_source) NOT IN ('UNCERTAIN','VERIFIED')
  THEN RAISE EXCEPTION 'upload cannot be retried'; END IF;
 RETURN health_writer.source_status(p_key,p_source);
END $fn$;

CREATE FUNCTION health_writer.begin_source_check(p_key text,p_source text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM health_writer.source_verifier_principals WHERE principal=session_user)
  THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='independent verifier required'; END IF;
 PERFORM pg_advisory_xact_lock(63741020261011);
 IF NOT EXISTS(SELECT 1 FROM health_writer.source_uploads u JOIN public.operations o USING(operation_id)
  WHERE u.request_key=p_key AND u.source_id=p_source AND u.state IN ('UNCERTAIN','VERIFIED') AND o.state='PREPARED')
  THEN RAISE EXCEPTION 'Source not eligible for verification'; END IF;
 -- Invalidate the old receipt BEFORE the external read. A failed read must not
 -- leave a previously valid receipt available for publication.
 UPDATE health_writer.source_uploads SET state='UNCERTAIN',candidate_sha=NULL,verifier=NULL,checked_at=NULL
  WHERE request_key=p_key AND source_id=p_source;
END $fn$;

CREATE FUNCTION health_writer.attest_source(p_key text,p_source text,p_marker uuid,p_object text,p_sha text,p_size bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u health_writer.source_uploads%rowtype; c health_writer.candidates%rowtype; m jsonb;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM health_writer.source_verifier_principals WHERE principal=session_user)
  THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='independent verifier required'; END IF;
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO u FROM health_writer.source_uploads WHERE request_key=p_key AND source_id=p_source FOR UPDATE;
 SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key FOR UPDATE;
 IF u.marker IS DISTINCT FROM p_marker OR u.state NOT IN ('UNCERTAIN','VERIFIED')
  OR (SELECT state FROM public.operations WHERE operation_id=u.operation_id) IS DISTINCT FROM 'PREPARED'
  OR c.candidate_sha IS NULL OR c.candidate_sha IS DISTINCT FROM health_writer.sha(c.payload)
  OR c.approved IS NOT TRUE OR c.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'invalid attestation binding'; END IF;
 IF jsonb_typeof(c.payload->'source_manifest') IS DISTINCT FROM 'array'
  OR (SELECT count(*) FROM jsonb_array_elements(c.payload->'source_manifest') x WHERE x->>'source_id'=p_source)<>1
  THEN RAISE EXCEPTION 'exact Source candidate required'; END IF;
 SELECT x INTO m FROM jsonb_array_elements(c.payload->'source_manifest') x WHERE x->>'source_id'=p_source;
 IF m->>'marker' IS DISTINCT FROM p_marker::text OR m->'source_row' IS DISTINCT FROM u.source_row
  OR m->>'provider' IS DISTINCT FROM u.provider OR m->>'account_alias' IS DISTINCT FROM u.account_alias
  OR m->>'object_id' IS DISTINCT FROM p_object OR p_object IS NULL OR p_object !~ '^[A-Za-z0-9_-]{8,128}$'
  OR (u.object_id IS NOT NULL AND u.object_id IS DISTINCT FROM p_object)
  THEN RAISE EXCEPTION 'provider identity binding conflict'; END IF;
 IF p_sha IS DISTINCT FROM u.source_row->>'sha256' OR p_size IS DISTINCT FROM (u.source_row->>'size_bytes')::bigint THEN
  UPDATE health_writer.source_uploads SET state='BLOCKED',safe_error='source_digest_or_length_mismatch'
   WHERE request_key=p_key AND source_id=p_source;
  RETURN jsonb_build_object('state','BLOCKED','protocol','HEALTH_WRITER_V1');
 END IF;
 UPDATE health_writer.source_uploads SET state='VERIFIED',object_id=p_object,candidate_sha=c.candidate_sha,
  verifier=session_user,checked_at=clock_timestamp(),safe_error=NULL WHERE request_key=p_key AND source_id=p_source;
 RETURN jsonb_build_object('state','VERIFIED','protocol','HEALTH_WRITER_V1');
END $fn$;

ALTER FUNCTION health_writer.finalize(text) RENAME TO finalize_delta;
REVOKE EXECUTE ON FUNCTION health_writer.finalize_delta(text) FROM health_writer_executor;
CREATE FUNCTION health_writer.finalize(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE c health_writer.candidates%rowtype; p health_writer.prepared_requests%rowtype;
 u health_writer.source_uploads%rowtype; m jsonb; result jsonb;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO p FROM health_writer.prepared_requests WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR p.caller IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key FOR UPDATE;
 IF EXISTS(SELECT 1 FROM health_writer.publish_audit WHERE request_key=p_key) THEN RETURN health_writer.finalize_delta(p_key); END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(c.payload->'changes') d WHERE d->>'table' IN ('sources','source_locations'))
  OR c.payload ? 'source_manifest' THEN
  IF jsonb_typeof(c.payload->'source_manifest') IS DISTINCT FROM 'array'
   OR jsonb_array_length(c.payload->'source_manifest')=0
   OR jsonb_array_length(c.payload->'source_manifest') IS DISTINCT FROM
    (SELECT count(*)::integer FROM jsonb_array_elements(c.payload->'changes') d WHERE d->>'table'='sources')
   OR jsonb_array_length(c.payload->'source_manifest') IS DISTINCT FROM
    (SELECT count(*)::integer FROM jsonb_array_elements(c.payload->'changes') d WHERE d->>'table'='source_locations')
   OR (SELECT count(DISTINCT x->>'source_id') FROM jsonb_array_elements(c.payload->'source_manifest') x)
     <>jsonb_array_length(c.payload->'source_manifest') THEN RAISE EXCEPTION 'Source manifest completeness conflict'; END IF;
  FOR m IN SELECT jsonb_array_elements(c.payload->'source_manifest') LOOP
   SELECT * INTO u FROM health_writer.source_uploads WHERE request_key=p_key AND source_id=m->>'source_id' FOR UPDATE;
   IF NOT FOUND OR u.operation_id IS DISTINCT FROM p.operation_id OR u.state IS DISTINCT FROM 'VERIFIED'
    OR u.candidate_sha IS DISTINCT FROM c.candidate_sha OR u.marker::text IS DISTINCT FROM m->>'marker'
    OR u.object_id IS DISTINCT FROM m->>'object_id' OR u.source_row IS DISTINCT FROM m->'source_row'
    OR u.provider IS DISTINCT FROM m->>'provider' OR u.account_alias IS DISTINCT FROM m->>'account_alias'
    OR u.checked_at IS NULL OR u.checked_at<clock_timestamp()-interval '10 minutes' OR u.checked_at>clock_timestamp()
    OR NOT EXISTS(SELECT 1 FROM health_writer.source_verifier_principals WHERE principal=u.verifier)
    OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(c.payload->'changes') d WHERE d->>'table'='sources'
      AND d->>'action'='INSERT' AND d->'row'=u.source_row)
    OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(c.payload->'changes') d WHERE d->>'table'='source_locations'
      AND d->>'action'='INSERT' AND d->'row'=m->'location_row'
      AND d->'row'->>'source_id'=u.source_id AND d->'row'->>'provider'=u.provider
      AND d->'row'->>'account_alias'=u.account_alias AND d->'row'->>'provider_object_id'=u.object_id
      AND d->'row'->>'location_role'='PRIMARY' AND d->'row'->>'verified_at' IS NOT NULL)
    THEN RAISE EXCEPTION 'Source verification missing/stale/conflicting'; END IF;
  END LOOP;
 END IF;
 result:=health_writer.finalize_delta(p_key);
 UPDATE health_writer.source_uploads SET state='PUBLISHED' WHERE request_key=p_key AND state='VERIFIED';
 RETURN result;
END $fn$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA health_writer FROM PUBLIC;
GRANT EXECUTE ON FUNCTION health_writer.plan_source(text,jsonb,text,text),health_writer.source_status(text,text),
 health_writer.source_uncertain(text,text),health_writer.finalize(text) TO health_writer_executor;
-- Administrator grants only attest_source + schema USAGE to a separate verifier.

-- Protected SQL upload journal; install after source_runtime.sql.
-- A trusted provisioner registers exact folders. Writer gets only these RPCs.
CREATE TABLE health_writer.upload_folders (
 folder text PRIMARY KEY CHECK(folder ~ '^[A-Za-z0-9_-]{8,128}$'),
 enabled boolean NOT NULL DEFAULT false
);
CREATE TABLE health_writer.source_upload_sessions (
 marker uuid PRIMARY KEY REFERENCES health_writer.source_uploads(marker),
 folder text NOT NULL REFERENCES health_writer.upload_folders(folder),
 state text NOT NULL CHECK(state IN ('PLANNED','STARTING','SESSION','COMPLETE')),
 session_uri text, object_id text, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK((state IN ('PLANNED','STARTING') AND session_uri IS NULL AND object_id IS NULL)
    OR (state='SESSION' AND session_uri IS NOT NULL AND object_id IS NULL)
    OR (state='COMPLETE' AND session_uri IS NOT NULL AND object_id IS NOT NULL))
);
ALTER TABLE health_writer.upload_folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.source_upload_sessions ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION health_writer.upload_guard(p_marker uuid,p_active boolean,p_locked boolean)
RETURNS health_writer.source_uploads LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u health_writer.source_uploads%rowtype; operation_state text;
 key bigint:=hashtextextended(p_marker::text,63741020261012);
BEGIN
 IF p_active THEN PERFORM health_writer.require_enabled(); END IF;
 SELECT x.* INTO u FROM health_writer.source_uploads x JOIN health_writer.prepared_requests p USING(request_key)
  WHERE x.marker=p_marker AND p.caller=session_user AND p.operation_id=x.operation_id;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='upload ownership denied'; END IF;
 SELECT state INTO operation_state FROM public.operations WHERE operation_id=u.operation_id;
 IF p_active AND (operation_state IS DISTINCT FROM 'PREPARED' OR u.state NOT IN ('PLANNED','UNCERTAIN','VERIFIED')
  OR NOT EXISTS(SELECT 1 FROM health_writer.writer_intents i WHERE i.request_key=u.request_key
   AND i.caller=session_user AND i.approved AND i.expires_at>clock_timestamp()))
 THEN RAISE EXCEPTION 'active authorized Source intent required'; END IF;
 IF p_locked AND NOT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory'
   AND database=(SELECT oid FROM pg_database WHERE datname=current_database())
   AND pid=pg_backend_pid() AND granted AND mode='ExclusiveLock' AND objsubid=1
   AND classid=((key >> 32) & 4294967295)::oid AND objid=(key & 4294967295)::oid)
 THEN RAISE EXCEPTION 'upload worker lock required'; END IF;
 IF p_locked AND NOT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory'
   AND database=(SELECT oid FROM pg_database WHERE datname=current_database())
   AND pid=pg_backend_pid() AND granted AND mode='ExclusiveLock' AND objsubid=1
   AND classid=((63741020261013::bigint >> 32) & 4294967295)::oid
   AND objid=(63741020261013::bigint & 4294967295)::oid)
 THEN RAISE EXCEPTION 'Source backup coordination lock required'; END IF;
 RETURN u;
END $fn$;

CREATE FUNCTION health_writer.upload_claim(p_marker uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM health_writer.upload_guard(p_marker,false,false);
 IF NOT pg_try_advisory_lock(63741020261013) THEN RETURN false; END IF;
 IF pg_try_advisory_lock(hashtextextended(p_marker::text,63741020261012)) THEN RETURN true; END IF;
 PERFORM pg_advisory_unlock(63741020261013); RETURN false;
END $fn$;
CREATE FUNCTION health_writer.upload_release(p_marker uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM health_writer.upload_guard(p_marker,false,true);
 IF NOT pg_advisory_unlock(hashtextextended(p_marker::text,63741020261012)) THEN RETURN false; END IF;
 RETURN pg_advisory_unlock(63741020261013);
END $fn$;
CREATE FUNCTION health_writer.upload_get(p_marker uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u health_writer.source_uploads%rowtype; j health_writer.source_upload_sessions%rowtype;
BEGIN
 u:=health_writer.upload_guard(p_marker,false,false);
 SELECT * INTO j FROM health_writer.source_upload_sessions WHERE marker=p_marker;
 IF NOT FOUND THEN RETURN NULL; END IF;
 RETURN jsonb_build_object('marker',p_marker,'folder',j.folder,'source_id',u.source_id,
  'sha256',u.source_row->>'sha256','size_bytes',(u.source_row->>'size_bytes')::bigint,
  'session_uri',j.session_uri,'object_id',j.object_id,'state',j.state);
END $fn$;
CREATE FUNCTION health_writer.upload_plan(p_marker uuid,p_folder text,p_source text,p_sha text,p_size bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u health_writer.source_uploads%rowtype; j health_writer.source_upload_sessions%rowtype;
BEGIN
 u:=health_writer.upload_guard(p_marker,false,true);
 IF p_source IS DISTINCT FROM u.source_id OR p_sha IS DISTINCT FROM u.source_row->>'sha256'
  OR p_size IS DISTINCT FROM (u.source_row->>'size_bytes')::bigint OR p_size<=0 OR p_size>1073741824
  OR u.provider IS DISTINCT FROM 'google-drive' THEN RAISE EXCEPTION 'upload Source binding conflict'; END IF;
 SELECT * INTO j FROM health_writer.source_upload_sessions WHERE marker=p_marker FOR UPDATE;
 IF FOUND THEN
  IF j.folder IS DISTINCT FROM p_folder THEN RAISE EXCEPTION 'upload folder binding conflict'; END IF;
  IF j.state<>'COMPLETE' THEN PERFORM health_writer.upload_guard(p_marker,true,true); END IF;
 ELSE
  PERFORM health_writer.upload_guard(p_marker,true,true);
  IF NOT EXISTS(SELECT 1 FROM health_writer.upload_folders f JOIN health_writer.runtime_policy p ON p.singleton AND p.primary_folder=f.folder WHERE f.folder=p_folder AND f.enabled)
   THEN RAISE EXCEPTION 'registered upload folder required'; END IF;
  INSERT INTO health_writer.source_upload_sessions(marker,folder,state) VALUES(p_marker,p_folder,'PLANNED');
 END IF;
 RETURN health_writer.upload_get(p_marker);
END $fn$;
CREATE FUNCTION health_writer.upload_authorize(p_marker uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM health_writer.upload_guard(p_marker,true,true);
 IF NOT EXISTS(SELECT 1 FROM health_writer.source_upload_sessions j
   JOIN health_writer.upload_folders f USING(folder) JOIN health_writer.runtime_policy p ON p.singleton AND p.primary_folder=f.folder WHERE j.marker=p_marker AND f.enabled
    AND j.state IN ('STARTING','SESSION'))
 THEN RAISE EXCEPTION 'authorized active upload session required'; END IF;
END $fn$;
CREATE FUNCTION health_writer.upload_description(p_marker uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u health_writer.source_uploads%rowtype;
BEGIN
 u:=health_writer.upload_guard(p_marker,true,true);
 RETURN u.source_row;
END $fn$;
CREATE FUNCTION health_writer.upload_starting(p_marker uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM health_writer.upload_guard(p_marker,true,true);
 UPDATE health_writer.source_upload_sessions j SET state='STARTING'
  WHERE marker=p_marker AND state='PLANNED'
   AND EXISTS(SELECT 1 FROM health_writer.upload_folders f WHERE f.folder=j.folder AND f.enabled);
 IF NOT FOUND THEN RAISE EXCEPTION 'upload initiation outcome uncertain or folder disabled'; END IF;
END $fn$;
CREATE FUNCTION health_writer.upload_session(p_marker uuid,p_uri text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 -- Save an already received provider reply even if approval expires meanwhile.
 -- No HTTP request is made here; upload_authorize guards each external request.
 PERFORM health_writer.upload_guard(p_marker,false,true);
 -- Python also validates the URL with a strict query parser before this call.
 -- Persist no foreign origin, fragment, duplicate/unknown query key or userinfo.
 IF p_uri IS NULL OR length(p_uri)>16384 OR p_uri ~ '[[:space:][:cntrl:]]'
  OR p_uri !~ '^https://www\.googleapis\.com/upload/drive/v3/files\?'
  OR substring(p_uri from '\?(.*)$') !~ '^(uploadType=resumable|upload_id=[A-Za-z0-9_%-]+|fields=[A-Za-z0-9_%,()-]+|session_crd=[A-Za-z0-9_%-]+)(&(uploadType=resumable|upload_id=[A-Za-z0-9_%-]+|fields=[A-Za-z0-9_%,()-]+|session_crd=[A-Za-z0-9_%-]+))*$'
  OR (SELECT count(*) FROM regexp_split_to_table(substring(p_uri from '\?(.*)$'),'&') x WHERE x='uploadType=resumable')<>1
  OR (SELECT count(*) FROM regexp_split_to_table(substring(p_uri from '\?(.*)$'),'&') x WHERE x LIKE 'upload_id=%')<>1
  OR (SELECT count(*) FROM regexp_split_to_table(substring(p_uri from '\?(.*)$'),'&') x WHERE x LIKE 'fields=%')>1
  OR (SELECT count(*) FROM regexp_split_to_table(substring(p_uri from '\?(.*)$'),'&') x WHERE x LIKE 'session_crd=%')>1
 THEN RAISE EXCEPTION 'upload session origin rejected'; END IF;
 UPDATE health_writer.source_upload_sessions SET state='SESSION',session_uri=p_uri
  WHERE marker=p_marker AND state='STARTING';
 IF NOT FOUND THEN RAISE EXCEPTION 'upload session transition rejected'; END IF;
END $fn$;
CREATE FUNCTION health_writer.upload_complete(p_marker uuid,p_object text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE j health_writer.source_upload_sessions%rowtype;
BEGIN
 PERFORM health_writer.upload_guard(p_marker,false,true);
 SELECT * INTO j FROM health_writer.source_upload_sessions WHERE marker=p_marker FOR UPDATE;
 IF NOT FOUND OR p_object IS NULL OR p_object !~ '^[A-Za-z0-9_-]{8,128}$'
  OR j.state NOT IN ('SESSION','COMPLETE') OR (j.object_id IS NOT NULL AND j.object_id IS DISTINCT FROM p_object)
 THEN RAISE EXCEPTION 'upload object binding conflict'; END IF;
 IF j.state='COMPLETE' THEN RETURN; END IF;
 UPDATE health_writer.source_upload_sessions SET state='COMPLETE',object_id=p_object WHERE marker=p_marker;
 -- COMPLETE is a transport fact only. It does not attest bytes or publish Source.
END $fn$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA health_writer FROM PUBLIC;
GRANT EXECUTE ON FUNCTION health_writer.upload_claim(uuid),health_writer.upload_release(uuid),
 health_writer.upload_get(uuid),health_writer.upload_plan(uuid,text,text,text,bigint),
 health_writer.upload_authorize(uuid),
 health_writer.upload_description(uuid),
 health_writer.upload_starting(uuid),health_writer.upload_session(uuid,text),
 health_writer.upload_complete(uuid,text) TO health_writer_executor;

-- TEST-only authorization bridge. Verified JWT claims arrive from a separate
-- trusted principal, never the normal writer. Semantic receipts are separate.
CREATE TABLE health_writer.approval_policy (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 principal name NOT NULL, actor_id text NOT NULL, repository_id text NOT NULL,
 workflow_sha text NOT NULL CHECK(workflow_sha ~ '^[a-f0-9]{40}$')
);
CREATE TABLE health_writer.approval_receipts (
 request_key text NOT NULL, kind text NOT NULL CHECK(kind IN ('intent','candidate')),
 digest text NOT NULL, actor_id text NOT NULL, workflow_sha text NOT NULL,
 token_jti text NOT NULL, run_id text NOT NULL, run_attempt text NOT NULL,
 accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(request_key,kind), UNIQUE(token_jti,kind)
);
ALTER TABLE health_writer.approval_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.approval_receipts ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION health_writer.accept_authorization(p_key text,p_kind text,p_digest text,p_actor text,
 p_repo text,p_workflow_sha text,p_jti text,p_run text,p_attempt text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE policy health_writer.approval_policy%rowtype; receipt health_writer.approval_receipts%rowtype;
 i health_writer.writer_intents%rowtype; c health_writer.candidates%rowtype;
BEGIN
 SELECT * INTO policy FROM health_writer.approval_policy WHERE singleton;
 IF policy.principal IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='trusted authorization bridge required'; END IF;
 IF policy.actor_id IS DISTINCT FROM p_actor OR policy.repository_id IS DISTINCT FROM p_repo
  OR policy.workflow_sha IS DISTINCT FROM p_workflow_sha OR p_kind IS NULL OR p_kind NOT IN ('intent','candidate')
  OR p_digest IS NULL OR p_digest !~ '^[a-f0-9]{64}$' OR p_jti IS NULL OR length(p_jti)<8 OR length(p_jti)>256
  OR p_run IS NULL OR p_run !~ '^[0-9]{1,20}$' OR p_attempt IS NULL OR p_attempt !~ '^[0-9]{1,6}$'
  THEN RAISE EXCEPTION 'authorization identity/pin mismatch'; END IF;
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO i FROM health_writer.writer_intents WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR i.intent_sha IS DISTINCT FROM health_writer.sha(i.intent) OR i.expires_at<=clock_timestamp()
  THEN RAISE EXCEPTION 'intent missing/changed/expired'; END IF;
 IF p_kind='candidate' THEN
  SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key FOR UPDATE;
  IF NOT FOUND OR i.approved IS NOT TRUE OR c.expires_at<=clock_timestamp()
   OR c.candidate_sha IS DISTINCT FROM health_writer.sha(c.payload) OR c.candidate_sha IS DISTINCT FROM p_digest
   OR c.payload->>'intent_sha' IS DISTINCT FROM i.intent_sha THEN RAISE EXCEPTION 'exact candidate binding conflict'; END IF;
 ELSIF i.intent_sha IS DISTINCT FROM p_digest THEN RAISE EXCEPTION 'exact intent binding conflict'; END IF;
 SELECT * INTO receipt FROM health_writer.approval_receipts WHERE request_key=p_key AND kind=p_kind;
 IF FOUND THEN
  IF receipt.digest IS DISTINCT FROM p_digest OR receipt.workflow_sha IS DISTINCT FROM p_workflow_sha
   THEN RAISE EXCEPTION 'approval replay binding conflict'; END IF;
  IF (p_kind='intent' AND i.approved IS NOT TRUE) OR (p_kind='candidate' AND c.approved IS NOT TRUE)
   THEN RAISE EXCEPTION 'approval revoked'; END IF;
  RETURN jsonb_build_object('accepted',true,'replayed',true,'digest',p_digest,'protocol','HEALTH_WRITER_V1');
 END IF;
 INSERT INTO health_writer.approval_receipts(request_key,kind,digest,actor_id,workflow_sha,token_jti,run_id,run_attempt)
  VALUES(p_key,p_kind,p_digest,p_actor,p_workflow_sha,p_jti,p_run,p_attempt);
 IF p_kind='intent' THEN UPDATE health_writer.writer_intents SET approved=true WHERE request_key=p_key;
 ELSE UPDATE health_writer.candidates SET approved=true WHERE request_key=p_key; END IF;
 RETURN jsonb_build_object('accepted',true,'replayed',false,'digest',p_digest,'protocol','HEALTH_WRITER_V1');
END $fn$;
CREATE FUNCTION health_writer.authorization_request(p_key text,p_kind text) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE i health_writer.writer_intents%rowtype; digest text;
BEGIN
 SELECT * INTO i FROM health_writer.writer_intents WHERE request_key=p_key;
 IF NOT FOUND OR i.caller IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 IF p_kind='intent' THEN digest:=i.intent_sha;
 ELSIF p_kind='candidate' THEN SELECT candidate_sha INTO digest FROM health_writer.candidates WHERE request_key=p_key;
 ELSE RAISE EXCEPTION 'invalid authorization kind'; END IF;
 IF digest IS NULL THEN RAISE EXCEPTION 'authorization target missing'; END IF;
 RETURN jsonb_build_object('request_key',p_key,'kind',p_kind,'digest',digest,'protocol','HEALTH_WRITER_V1');
END $fn$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA health_writer FROM PUBLIC;
GRANT EXECUTE ON FUNCTION health_writer.authorization_request(text,text) TO health_writer_executor;

-- Canonical API candidate; installed disabled. No bootstrap clinical write.
CREATE TABLE health_writer.runtime_policy (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 enabled boolean NOT NULL DEFAULT false,
 code_sha text CHECK(code_sha ~ '^[a-f0-9]{40}$'),
 migration_operation uuid NOT NULL,
 primary_folder text CHECK(primary_folder ~ '^[A-Za-z0-9_-]{8,128}$'),
 CHECK(NOT enabled OR code_sha IS NOT NULL)
);
INSERT INTO health_writer.runtime_policy(singleton,enabled,migration_operation)
 VALUES(true,false,'fa39e51f-3d95-4f82-bd3b-94438e7139a1');
CREATE TABLE health_writer.semantic_verifier_principals (principal name PRIMARY KEY);
CREATE TABLE health_writer.lab_check_context (
 backend integer PRIMARY KEY, transaction_id xid8 NOT NULL, request_key text NOT NULL,
 candidate_sha text NOT NULL, after_sha text NOT NULL
);
CREATE TABLE health_writer.lab_evidence (
 request_key text REFERENCES health_writer.candidates(request_key),
 lab_id bigint, literal_row jsonb NOT NULL, candidate_sha text NOT NULL,
 evidence_sha text NOT NULL, verifier name NOT NULL, checked_at timestamptz NOT NULL,
 PRIMARY KEY(request_key,lab_id)
);
ALTER TABLE health_writer.runtime_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.semantic_verifier_principals ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.lab_check_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_writer.lab_evidence ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION health_writer.require_enabled() RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM health_writer.runtime_policy p
   JOIN public.operations o ON o.operation_id=p.migration_operation
   WHERE p.singleton AND p.enabled AND p.code_sha IS NOT NULL
     AND o.state='FINALIZED' AND o.result='PASS' AND o.finalized_at IS NOT NULL
     AND EXISTS(SELECT 1 FROM health_writer.upload_folders f WHERE f.folder=p.primary_folder AND f.enabled)
     AND EXISTS(SELECT 1 FROM health_writer.approval_policy a WHERE a.singleton AND a.workflow_sha=p.code_sha))
 THEN RAISE EXCEPTION 'Writer disabled or migration not finalized'; END IF;
 IF NOT health_writer.records_schema_valid() THEN RAISE EXCEPTION 'immutable baseline or record schema changed'; END IF;
 IF NOT pg_try_advisory_xact_lock(63741020261013) THEN
  RAISE EXCEPTION 'Source capture or another worker active'; END IF;
END $fn$;

-- An exact chat command is immutable. The separate authorization bridge verifies
-- actor, repository, workflow, commit and JWT before granting intent/candidate.
CREATE FUNCTION health_writer.submit_intent(p_key text,p_intent jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE i health_writer.writer_intents%rowtype; digest text;
BEGIN
 PERFORM health_writer.require_enabled();
 IF p_key IS NULL OR p_key !~ '^[A-Za-z0-9_-]{8,128}$'
   OR jsonb_typeof(p_intent) IS DISTINCT FROM 'object'
   OR p_intent->>'user_message_sha256' IS NULL
   OR p_intent->>'user_message_sha256' !~ '^[a-f0-9]{64}$'
   OR nullif(p_intent->>'conversation_ref','') IS NULL
   OR length(p_intent->>'conversation_ref')>256
   OR p_intent->>'action' IS NULL OR p_intent->>'action' NOT IN ('CREATE_REC','UPDATE')
   OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_intent) k WHERE k NOT IN
      ('action','record_date','user_message_sha256','conversation_ref'))
 THEN RAISE EXCEPTION 'invalid owner intent'; END IF;
 IF p_intent->>'action'='CREATE_REC' AND ((p_intent->>'record_date')::date IS NULL
    OR ((p_intent->>'record_date')::date)::text IS DISTINCT FROM p_intent->>'record_date')
 THEN RAISE EXCEPTION 'exact record date required'; END IF;
 IF p_intent->>'action'='UPDATE' AND p_intent ? 'record_date' THEN
  RAISE EXCEPTION 'unexpected record date'; END IF;
 digest:=health_writer.sha(p_intent);
 SELECT * INTO i FROM health_writer.writer_intents WHERE request_key=p_key FOR UPDATE;
 IF FOUND THEN
  IF i.caller IS DISTINCT FROM session_user OR i.intent IS DISTINCT FROM p_intent
    OR i.intent_sha IS DISTINCT FROM digest THEN RAISE EXCEPTION 'intent replay conflict'; END IF;
 ELSE
  INSERT INTO health_writer.writer_intents VALUES(p_key,session_user,p_intent,digest,false,clock_timestamp()+interval '30 minutes');
 END IF;
 RETURN jsonb_build_object('request_key',p_key,'intent_sha',digest,'approved',false);
END $fn$;

-- All insert columns must be supplied: projection cannot consume sequence values
-- or evaluate clock defaults that differ between planning and publication.
CREATE FUNCTION health_writer.check_changes(p_changes jsonb) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE d jsonb; tab regclass;
BEGIN
 IF jsonb_typeof(p_changes) IS DISTINCT FROM 'array' OR jsonb_array_length(p_changes) NOT BETWEEN 1 AND 100
 THEN RAISE EXCEPTION 'bounded nonempty changes required'; END IF;
 FOR d IN SELECT jsonb_array_elements(p_changes) LOOP
  IF d->>'table' IS NULL OR d->>'table' NOT IN
   ('records','cases','case_links','labs','medications','monitoring','plan_items','questions','record_domains','record_sources','sources','source_locations')
  THEN RAISE EXCEPTION 'unsupported clinical table'; END IF;
  tab:=to_regclass('public.'||(d->>'table'));
  IF EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid=tab AND NOT tgisinternal AND tgenabled<>'D')
  THEN RAISE EXCEPTION 'unreviewed clinical trigger'; END IF;
  IF d->>'action'='INSERT' AND (jsonb_typeof(d->'row') IS DISTINCT FROM 'object'
   OR EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=tab AND a.attnum>0 AND NOT a.attisdropped
     AND (a.attgenerated<>'' OR NOT (d->'row' ? a.attname))))
  THEN RAISE EXCEPTION 'explicit deterministic insert columns required'; END IF;
 END LOOP;
END $fn$;

CREATE FUNCTION health_writer.propose(p_key text,p_changes jsonb,p_manifest jsonb DEFAULT NULL) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p health_writer.prepared_requests%rowtype; i health_writer.writer_intents%rowtype;
 c health_writer.candidates%rowtype; b jsonb; a jsonb; payload jsonb; pinned_time timestamptz:=clock_timestamp();
BEGIN
 PERFORM health_writer.require_enabled();
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO p FROM health_writer.prepared_requests WHERE request_key=p_key FOR UPDATE;
 SELECT * INTO i FROM health_writer.writer_intents WHERE request_key=p_key FOR UPDATE;
 IF p.caller IS DISTINCT FROM session_user OR p.operation_class IS DISTINCT FROM 'HEALTH_WRITER_DELTA_V1'
  OR i.approved IS NOT TRUE OR i.expires_at<=clock_timestamp()
  OR i.intent_sha IS DISTINCT FROM p.intent_sha OR i.intent_sha IS DISTINCT FROM health_writer.sha(i.intent)
  OR (SELECT state FROM public.operations WHERE operation_id=p.operation_id) IS DISTINCT FROM 'PREPARED'
 THEN RAISE EXCEPTION 'active owner-bound preparation required'; END IF;
 PERFORM health_writer.check_changes(p_changes);
 SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key FOR UPDATE;
 IF FOUND THEN
  IF c.payload->'changes' IS DISTINCT FROM p_changes OR c.payload->'source_manifest' IS DISTINCT FROM p_manifest
  THEN RAISE EXCEPTION 'candidate replay conflict'; END IF;
  RETURN jsonb_build_object('candidate_sha',c.candidate_sha,'before_sha',c.expected_before_sha,'after_sha',c.expected_after_sha);
 END IF;
 LOCK TABLE public.records,public.domains,public.record_domains,public.sources,public.source_locations,
  public.record_sources,public.cases,public.case_links,public.analytes,public.labs,public.medications,
  public.monitoring,public.plan_items,public.questions,public.id_reservations IN SHARE ROW EXCLUSIVE MODE;
 b:=health_writer.checkpoint();
 IF p.nnn IS NULL AND EXISTS(SELECT 1 FROM jsonb_array_elements(p_changes) d
  WHERE d->>'table'='records' AND d->>'action'='INSERT') THEN RAISE EXCEPTION 'unexpected REC allocation'; END IF;
 BEGIN
  PERFORM health_writer.apply_delta_internal(p_changes,p.operation_id);
  UPDATE public.id_reservations SET state='used',record_id=metadata->>'proposed_record_id',updated_at=pinned_time
   WHERE operation_id=p.operation_id AND state='reserved';
  a:=health_writer.checkpoint();
  IF NOT health_writer.records_schema_valid() THEN RAISE EXCEPTION 'record schema or immutable legacy exception invalid'; END IF;
  RAISE EXCEPTION USING ERRCODE='P0099',MESSAGE='projection rollback';
 EXCEPTION WHEN SQLSTATE 'P0099' THEN NULL; END;
 payload:=jsonb_build_object('changes',p_changes,'intent_sha',p.intent_sha,'ledger_updated_at',pinned_time);
 IF p_manifest IS NOT NULL THEN payload:=payload||jsonb_build_object('source_manifest',p_manifest); END IF;
 INSERT INTO health_writer.candidates VALUES(p_key,payload,health_writer.sha(payload),false,
  least(i.expires_at,clock_timestamp()+interval '10 minutes'),health_writer.sha(b),health_writer.sha(a));
 INSERT INTO health_writer.candidate_projections VALUES(p_key,b,a);
 RETURN jsonb_build_object('candidate_sha',health_writer.sha(payload),'before_sha',health_writer.sha(b),'after_sha',health_writer.sha(a));
END $fn$;

CREATE FUNCTION health_writer.lab_literal(p_row jsonb) RETURNS jsonb
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,pg_temp AS $fn$
 SELECT jsonb_build_array(p_row->'record_id',p_row->'observed_on',p_row->'analyte_key',p_row->'value',
 p_row->'unit',p_row->'reference_range',p_row->'flag',p_row->'source_name',p_row->'note');
$fn$;
CREATE FUNCTION health_writer.validate_lab_delta(p_key text,p_before jsonb,p_after jsonb) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE c health_writer.candidates%rowtype; row jsonb; old jsonb; e health_writer.lab_evidence%rowtype;
BEGIN
 SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key;
 FOR row IN SELECT jsonb_array_elements(p_after->'labs') LOOP
  SELECT x INTO old FROM jsonb_array_elements(p_before->'labs') x WHERE x->'lab_id'=row->'lab_id';
  IF old IS DISTINCT FROM row THEN
   SELECT * INTO e FROM health_writer.lab_evidence WHERE request_key=p_key AND lab_id=(row->>'lab_id')::bigint;
   IF e.candidate_sha IS DISTINCT FROM c.candidate_sha OR e.literal_row IS DISTINCT FROM health_writer.lab_literal(row)
    OR e.checked_at IS NULL OR e.checked_at<=clock_timestamp()-interval '10 minutes' OR e.checked_at>clock_timestamp()
    OR NOT EXISTS(SELECT 1 FROM health_writer.semantic_verifier_principals WHERE principal=e.verifier)
   THEN RAISE EXCEPTION 'changed lab literal evidence missing'; END IF;
  END IF;
 END LOOP;
 INSERT INTO health_writer.lab_check_context VALUES(pg_backend_pid(),pg_current_xact_id(),p_key,c.candidate_sha,health_writer.sha(p_after))
  ON CONFLICT(backend) DO UPDATE SET transaction_id=excluded.transaction_id,request_key=excluded.request_key,
   candidate_sha=excluded.candidate_sha,after_sha=excluded.after_sha;
END $fn$;
CREATE OR REPLACE FUNCTION health_writer.lab_check_context_valid() RETURNS boolean
LANGUAGE sql STABLE SET search_path=pg_catalog,pg_temp AS $fn$
 SELECT EXISTS(SELECT 1 FROM health_writer.lab_check_context c WHERE c.backend=pg_backend_pid()
  AND c.transaction_id=pg_current_xact_id_if_assigned() AND c.after_sha=health_writer.sha(health_writer.checkpoint()));
$fn$;

CREATE FUNCTION health_writer.attest_semantics(p_key text,p_candidate text,p_after text,p_receipts jsonb,p_labs jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE c health_writer.candidates%rowtype; r jsonb; i integer;
BEGIN
 PERFORM health_writer.require_enabled();
 IF NOT EXISTS(SELECT 1 FROM health_writer.semantic_verifier_principals WHERE principal=session_user)
  OR EXISTS(SELECT 1 FROM health_writer.prepared_requests WHERE request_key=p_key AND caller=session_user)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='independent semantic verifier required'; END IF;
 SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key FOR UPDATE;
 IF c.candidate_sha IS DISTINCT FROM p_candidate OR c.expected_after_sha IS DISTINCT FROM p_after
  OR c.approved IS NOT TRUE OR c.expires_at<=clock_timestamp()
  OR c.candidate_sha IS DISTINCT FROM health_writer.sha(c.payload)
 THEN RAISE EXCEPTION 'exact approved candidate required'; END IF;
 IF jsonb_typeof(p_receipts) IS DISTINCT FROM 'array' OR jsonb_array_length(p_receipts)<>10
  OR (SELECT count(DISTINCT (x->>'rule_id')::integer) FROM jsonb_array_elements(p_receipts) x
   WHERE (x->>'rule_id')::integer IN (19,20,21,22,27,28,29,30,31,37))<>10
  OR jsonb_typeof(p_labs) IS DISTINCT FROM 'array' OR jsonb_array_length(p_labs)>100
 THEN RAISE EXCEPTION 'complete bounded semantic receipts required'; END IF;
 DELETE FROM health_writer.semantic_receipts WHERE request_key=p_key;
 DELETE FROM health_writer.lab_evidence WHERE request_key=p_key;
 FOR r IN SELECT jsonb_array_elements(p_receipts) LOOP
  IF r->>'status' IS DISTINCT FROM 'PASS' OR r->>'evidence_sha' IS NULL
    OR r->>'evidence_sha' !~ '^[a-f0-9]{64}$' OR nullif(r->>'methodology','') IS NULL
    OR length(r->>'methodology')>2000 THEN RAISE EXCEPTION 'invalid semantic receipt'; END IF;
  INSERT INTO health_writer.semantic_receipts VALUES(p_key,(r->>'rule_id')::integer,p_candidate,p_after,
    r->>'evidence_sha','PASS',r->>'methodology',clock_timestamp());
 END LOOP;
 FOR r IN SELECT jsonb_array_elements(p_labs) LOOP
  IF r->>'evidence_sha' IS NULL OR r->>'evidence_sha' !~ '^[a-f0-9]{64}$'
    OR jsonb_typeof(r->'literal_row') IS DISTINCT FROM 'array' OR jsonb_array_length(r->'literal_row')<>9
  THEN RAISE EXCEPTION 'invalid lab evidence'; END IF;
  INSERT INTO health_writer.lab_evidence VALUES(p_key,(r->>'lab_id')::bigint,r->'literal_row',p_candidate,
    r->>'evidence_sha',session_user,clock_timestamp());
 END LOOP;
 RETURN jsonb_build_object('candidate_sha',p_candidate,'receipts',10);
END $fn$;

-- Private helpers retain session_user. No caller can execute an inner bypass.
ALTER FUNCTION health_writer.prepare(text) RENAME TO prepare_inner;
ALTER FUNCTION health_writer.finalize(text) RENAME TO finalize_inner;
ALTER FUNCTION health_writer.abandon(text) RENAME TO abandon_inner;
ALTER FUNCTION health_writer.plan_source(text,jsonb,text,text) RENAME TO plan_source_inner;
ALTER FUNCTION health_writer.source_uncertain(text,text) RENAME TO source_uncertain_inner;
CREATE FUNCTION health_writer.prepare(p_key text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN PERFORM health_writer.require_enabled(); RETURN health_writer.prepare_inner(p_key); END $fn$;
CREATE FUNCTION health_writer.finalize(p_key text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN PERFORM health_writer.require_enabled(); RETURN health_writer.finalize_inner(p_key); END $fn$;
CREATE FUNCTION health_writer.abandon(p_key text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN PERFORM health_writer.require_enabled(); RETURN health_writer.abandon_inner(p_key); END $fn$;
CREATE FUNCTION health_writer.plan_source(p_key text,p_source jsonb,p_provider text,p_account text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM health_writer.require_enabled();
 IF p_provider IS DISTINCT FROM 'google-drive' OR p_account IS DISTINCT FROM 'HEALTH_PRIMARY' THEN RAISE EXCEPTION 'canonical provider required'; END IF;
 RETURN health_writer.plan_source_inner(p_key,p_source,p_provider,p_account);
END $fn$;
CREATE FUNCTION health_writer.source_uncertain(p_key text,p_source text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN PERFORM health_writer.require_enabled(); RETURN health_writer.source_uncertain_inner(p_key,p_source); END $fn$;

REVOKE ALL ON ALL TABLES IN SCHEMA health_writer FROM PUBLIC,anon,authenticated,service_role,health_writer_executor,health_writer_authorizer,health_writer_verifier;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA health_writer FROM PUBLIC,anon,authenticated,service_role,health_writer_executor,health_writer_authorizer,health_writer_verifier;
GRANT USAGE ON SCHEMA health_writer TO health_writer_executor,health_writer_authorizer,health_writer_verifier;
GRANT EXECUTE ON FUNCTION health_writer.submit_intent(text,jsonb),health_writer.prepare(text),health_writer.propose(text,jsonb,jsonb),
 health_writer.finalize(text),health_writer.abandon(text),health_writer.request_status(text),health_writer.authorization_request(text,text),
 health_writer.plan_source(text,jsonb,text,text),health_writer.source_status(text,text),health_writer.source_uncertain(text,text),
 health_writer.upload_claim(uuid),health_writer.upload_release(uuid),health_writer.upload_get(uuid),
 health_writer.upload_plan(uuid,text,text,text,bigint),health_writer.upload_starting(uuid),health_writer.upload_session(uuid,text),
 health_writer.upload_complete(uuid,text),health_writer.upload_authorize(uuid),health_writer.upload_description(uuid)
 TO health_writer_executor;
GRANT EXECUTE ON FUNCTION health_writer.accept_authorization(text,text,text,text,text,text,text,text,text) TO health_writer_authorizer;
GRANT EXECUTE ON FUNCTION health_writer.attest_semantics(text,text,text,jsonb,jsonb),
 health_writer.begin_source_check(text,text),health_writer.attest_source(text,text,uuid,text,text,bigint) TO health_writer_verifier;

-- Private read models for the chat worker and the distinct verifier. These
-- routines never expose a general SQL interface or grant direct table access.
CREATE TABLE health_writer.candidate_projections (
 request_key text PRIMARY KEY REFERENCES health_writer.candidates(request_key),
 before_state jsonb NOT NULL, after_state jsonb NOT NULL
);
ALTER TABLE health_writer.candidate_projections ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE health_writer.candidate_projections FROM PUBLIC,anon,authenticated,service_role,health_writer_executor,health_writer_authorizer,health_writer_verifier;

CREATE FUNCTION health_writer.snapshot_row_hashes(p_state jsonb) RETURNS jsonb
LANGUAGE sql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $fn$
 SELECT coalesce(jsonb_object_agg(k,(SELECT coalesce(jsonb_agg(health_writer.sha(row) ORDER BY ord),'[]'::jsonb)
  FROM jsonb_array_elements(rows) WITH ORDINALITY AS x(row,ord))),'{}'::jsonb)
 FROM jsonb_each(p_state) AS tables(k,rows);
$fn$;
REVOKE ALL ON FUNCTION health_writer.snapshot_row_hashes(jsonb) FROM PUBLIC,anon,authenticated,service_role,health_writer_executor,health_writer_authorizer,health_writer_verifier;

CREATE FUNCTION health_writer.request_context(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE i health_writer.writer_intents%rowtype; context jsonb;
BEGIN
 PERFORM health_writer.require_enabled();
 SELECT * INTO i FROM health_writer.writer_intents WHERE request_key=p_key;
 IF NOT FOUND OR i.caller IS DISTINCT FROM session_user OR NOT i.approved
  OR i.expires_at<=clock_timestamp() OR i.intent_sha IS DISTINCT FROM health_writer.sha(i.intent)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='active owned intent required'; END IF;
 context:=health_writer.checkpoint();
 RETURN jsonb_build_object('request_key',p_key,'intent',i.intent,'intent_sha',i.intent_sha,
  'context',context,'row_hashes',health_writer.snapshot_row_hashes(context),
  'legacy_exceptions',health_writer.legacy_record_exception_report());
END $fn$;

CREATE FUNCTION health_writer.review_candidate(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE c health_writer.candidates%rowtype; p health_writer.prepared_requests%rowtype;
 v health_writer.candidate_projections%rowtype;
BEGIN
 PERFORM health_writer.require_enabled();
 IF NOT EXISTS(SELECT 1 FROM health_writer.semantic_verifier_principals WHERE principal=session_user)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='independent verifier required'; END IF;
 SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key;
 SELECT * INTO p FROM health_writer.prepared_requests WHERE request_key=p_key;
 SELECT * INTO v FROM health_writer.candidate_projections WHERE request_key=p_key;
 IF c.request_key IS NULL OR p.caller=session_user OR NOT c.approved OR c.expires_at<=clock_timestamp()
  OR (SELECT state FROM public.operations WHERE operation_id=p.operation_id) IS DISTINCT FROM 'PREPARED'
  OR c.candidate_sha IS DISTINCT FROM health_writer.sha(c.payload)
  OR c.expected_before_sha IS DISTINCT FROM health_writer.sha(v.before_state)
  OR c.expected_after_sha IS DISTINCT FROM health_writer.sha(v.after_state)
 THEN RAISE EXCEPTION 'exact approved candidate review unavailable'; END IF;
 RETURN jsonb_build_object('request_key',p_key,'operation_id',p.operation_id,'candidate_sha',c.candidate_sha,
  'before_sha',c.expected_before_sha,'after_sha',c.expected_after_sha,'payload',c.payload,
  'before_state',v.before_state,'after_state',v.after_state,
  'legacy_exceptions',health_writer.legacy_record_exception_report());
END $fn$;
REVOKE ALL ON FUNCTION health_writer.request_context(text),health_writer.review_candidate(text) FROM PUBLIC,anon,authenticated,service_role,health_writer_executor,health_writer_authorizer,health_writer_verifier;
GRANT EXECUTE ON FUNCTION health_writer.request_context(text) TO health_writer_executor;
GRANT EXECUTE ON FUNCTION health_writer.review_candidate(text) TO health_writer_verifier;

-- Separate namespaced routine rules. Existing migration/PWA checks are retained.
INSERT INTO public.validation_checks(check_key,mechanism,description,dependencies,active)
 SELECT 'WRITER_V1_RULE_'||lpad(i::text,2,'0'),'OPERATION_AUDIT',description,ARRAY[]::text[],true
 FROM unnest(ARRAY[
 'Unique record_id','Known domains','Case keys resolve to Records','Case lifecycle normalized',
 'Closed cases have closing REC','Labs resolve to Records','Analytes resolve','ID ledger coverage',
 'Binary active Sources through registered Google folder','Owner GitHub identity and exact workflow/code binding',
 'Records active schema','No archive tree writes','Markdown rendering is outside typed SQL operation',
 'Routine operation transaction schema','Verified durable Source publication or unchanged Source graph',
 'Finalized migration baseline','Physical original/archive purge unavailable',
 'Changed lab literals independently attested; unchanged rows preserved',
 'Historical full-text materialization','Active source-file independence','Labs derived-layer exact audit',
 'Documentation consistency audit','Single-writer invariant','Exact operation audit stamps complete',
 'Canonical analyte keys unique','Labs exact duplicate rows','Case Links semantic audit',
 'Current-state semantic audit','Source originals retention audit','Records provenance audit',
 'Analyte canonicalization audit','ID ledger exact REC mapping','Case identity invariant',
 'Case status and closing consistency','Case Links triple uniqueness','Operation audit references resolve',
 'Records case_keys match Case Links'
 ]) WITH ORDINALITY AS rules(description,i);

CREATE FUNCTION health_writer.register_validation(p_key text) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p health_writer.prepared_requests%rowtype; a health_writer.publish_audit%rowtype;
 c health_writer.candidates%rowtype; i integer; status text; detail jsonb;
BEGIN
 SELECT * INTO p FROM health_writer.prepared_requests WHERE request_key=p_key;
 SELECT * INTO a FROM health_writer.publish_audit WHERE request_key=p_key;
 SELECT * INTO c FROM health_writer.candidates WHERE request_key=p_key;
 IF p.caller IS DISTINCT FROM session_user OR p.operation_class IS DISTINCT FROM 'HEALTH_WRITER_DELTA_V1'
  OR a.operation_id IS DISTINCT FROM p.operation_id OR c.candidate_sha IS DISTINCT FROM a.candidate_sha
  OR a.after_sha IS DISTINCT FROM health_writer.sha(health_writer.checkpoint())
  OR (SELECT state FROM public.operations WHERE operation_id=p.operation_id) IS DISTINCT FROM 'FINALIZED'
  OR (SELECT count(*) FROM health_writer.writer_validation_results WHERE operation_id=p.operation_id
    AND candidate_sha=a.candidate_sha AND after_sha=a.after_sha)<>30
  OR (SELECT count(*) FROM health_writer.structural_checks())<>20
  OR EXISTS(SELECT 1 FROM health_writer.structural_checks() WHERE passed IS DISTINCT FROM true)
 THEN RAISE EXCEPTION 'operation-bound canonical validation incomplete'; END IF;
 IF (SELECT count(*) FROM health_writer.approval_receipts WHERE request_key=p_key
  AND workflow_sha=(SELECT code_sha FROM health_writer.runtime_policy WHERE singleton)
  AND actor_id=(SELECT actor_id FROM health_writer.approval_policy WHERE singleton)
  AND ((kind='intent' AND digest=p.intent_sha) OR (kind='candidate' AND digest=a.candidate_sha)))<>2
 THEN RAISE EXCEPTION 'exact owner authorization receipts missing'; END IF;
 IF EXISTS(SELECT 1 FROM health_writer.source_uploads u WHERE request_key=p_key
  AND (u.state IS DISTINCT FROM 'PUBLISHED' OR u.provider IS DISTINCT FROM 'google-drive'
    OR u.account_alias IS DISTINCT FROM 'HEALTH_PRIMARY' OR u.candidate_sha IS DISTINCT FROM a.candidate_sha
    OR NOT EXISTS(SELECT 1 FROM health_writer.source_upload_sessions s JOIN health_writer.upload_folders f USING(folder)
       WHERE s.marker=u.marker AND s.state='COMPLETE' AND s.object_id=u.object_id AND f.enabled)))
 THEN RAISE EXCEPTION 'canonical durable Source publication incomplete'; END IF;
 FOR i IN 1..37 LOOP
  status:=CASE WHEN i=13 THEN 'SKIP' ELSE 'PASS' END;
  detail:=jsonb_build_object('protocol','HEALTH_WRITER_V1','operation_id',p.operation_id,
    'intent_sha',p.intent_sha,'candidate_sha',a.candidate_sha,'before_sha',a.before_sha,'after_sha',a.after_sha,
    'code_sha',(SELECT code_sha FROM health_writer.runtime_policy WHERE singleton),
    'rule_id',i,'basis',CASE
       WHEN i=13 THEN 'Plain body_text SQL mutation; Markdown renderer is outside this operation'
       WHEN i IN (9,12,15,17) THEN 'Create-only registered provider objects; no original/archive update or physical purge API'
       WHEN i=10 THEN 'Both exact owner actor/workflow/commit approval receipts verified'
       WHEN i=16 THEN 'Exact historical migration remains FINALIZED/PASS; routine class is separate'
       WHEN i IN (19,20,21,22,27,28,29,30,31,37) THEN 'Fresh independent candidate/after-state semantic receipt'
       ELSE 'Structural evaluation and immutable operation audit in the publication transaction' END);
  IF i IN (19,20,21,22,27,28,29,30,31,37) THEN
   detail:=detail||(SELECT jsonb_build_object('evidence_sha',evidence_sha,'methodology',methodology,'receipt_checked_at',checked_at)
     FROM health_writer.semantic_receipts WHERE request_key=p_key AND rule_id=i);
  END IF;
  IF i=11 THEN
   detail:=detail||jsonb_build_object('legacy_id_date_exceptions',health_writer.legacy_record_exception_report());
  END IF;
  INSERT INTO public.validation_results(operation_id,check_key,status,checked_at,details)
   VALUES(p.operation_id,'WRITER_V1_RULE_'||lpad(i::text,2,'0'),status,clock_timestamp(),detail);
 END LOOP;
 DELETE FROM health_writer.lab_check_context WHERE backend=pg_backend_pid();
END $fn$;

CREATE OR REPLACE FUNCTION health_writer.finalize(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE result jsonb;
BEGIN
 PERFORM health_writer.require_enabled();
 result:=health_writer.finalize_inner(p_key);
 IF (result->>'replayed')::boolean IS NOT TRUE THEN PERFORM health_writer.register_validation(p_key); END IF;
 RETURN result;
END $fn$;
REVOKE ALL ON FUNCTION health_writer.register_validation(text) FROM PUBLIC,anon,authenticated,service_role,health_writer_executor,health_writer_authorizer,health_writer_verifier;


DO $baseline$ BEGIN
 IF (SELECT count(*) FROM public.records WHERE substring(record_id,5,8)<>to_char(record_date,'YYYYMMDD'))<>1
 OR (SELECT health_writer.sha(coalesce(jsonb_agg(to_jsonb(r) ORDER BY record_id),'[]'::jsonb)) FROM public.records r WHERE substring(record_id,5,8)<>to_char(record_date,'YYYYMMDD')) IS DISTINCT FROM '89e0d06e67f2a7f466a987013073d1336ea7747dd08e5a0b8cbe994c0ec89f04'
 THEN RAISE EXCEPTION 'exact owner-approved legacy baseline changed'; END IF;
END $baseline$;
INSERT INTO health_writer.legacy_record_exceptions
 SELECT true,record_id,health_writer.sha(to_jsonb(r)),'89e0d06e67f2a7f466a987013073d1336ea7747dd08e5a0b8cbe994c0ec89f04','381236f2ab89c93e006db16ad677998f962ea9327b28185787037e1ee230ff90','chat:call_9d1ebf2674ad4626b9bcca3a96eea335:owner_reply',true
 FROM public.records r WHERE substring(record_id,5,8)<>to_char(record_date,'YYYYMMDD');
DO $valid$ BEGIN IF NOT health_writer.records_schema_valid() THEN RAISE EXCEPTION 'canonical records schema or legacy binding invalid'; END IF; END $valid$;
-- Fixed private destination, callable only through the server authorization
-- role. No Writer login, anonymous or authenticated client can invoke it.
CREATE FUNCTION public.health_writer_authorize_v1(p_key text,p_kind text,p_digest text,p_actor text,
 p_repo text,p_workflow_sha text,p_jti text,p_run text,p_attempt text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE claims jsonb;
BEGIN
 claims:=coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
 IF session_user<>'authenticator' OR claims->>'role' IS DISTINCT FROM 'service_role' THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='server-only authorization bridge required'; END IF;
 IF p_key IS NULL OR p_key !~ '^writer-[a-f0-9]{32}$' THEN RAISE EXCEPTION 'opaque request identity required'; END IF;
 PERFORM health_writer.require_enabled();
 RETURN health_writer.accept_authorization(p_key,p_kind,p_digest,p_actor,p_repo,p_workflow_sha,p_jti,p_run,p_attempt);
END $fn$;
REVOKE ALL ON FUNCTION public.health_writer_authorize_v1(text,text,text,text,text,text,text,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.health_writer_authorize_v1(text,text,text,text,text,text,text,text,text) TO service_role;

COMMIT;