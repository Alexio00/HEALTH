-- TEST-only delta engine. Fixed schema rendered by build_fixture.py.
-- The approval/semantic-verifier input in this fixture is explicitly simulated.
-- This file does not deploy to public or authorize clinical operations.
CREATE TABLE __SCHEMA__.candidates (
 request_key text PRIMARY KEY, payload jsonb NOT NULL, candidate_sha text NOT NULL,
 approved boolean NOT NULL DEFAULT false, expires_at timestamptz NOT NULL,
 expected_before_sha text NOT NULL, expected_after_sha text NOT NULL
);
CREATE TABLE __SCHEMA__.semantic_receipts (
 request_key text REFERENCES __SCHEMA__.candidates(request_key), rule_id integer,
 candidate_sha text NOT NULL, after_sha text NOT NULL, evidence_sha text NOT NULL,
 status text NOT NULL, methodology text NOT NULL, checked_at timestamptz NOT NULL,
 PRIMARY KEY(request_key,rule_id)
);
CREATE TABLE __SCHEMA__.expected_labs (lab_id bigint PRIMARY KEY, literal_row jsonb NOT NULL);
CREATE TABLE __SCHEMA__.publish_audit (
 request_key text PRIMARY KEY, operation_id uuid NOT NULL, candidate_sha text NOT NULL, before_state jsonb NOT NULL,
 after_state jsonb NOT NULL, before_sha text NOT NULL, after_sha text NOT NULL
);
CREATE FUNCTION __SCHEMA__.checkpoint() RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE t text; result jsonb='{}'; rows jsonb;
BEGIN
 FOREACH t IN ARRAY ARRAY['records','domains','record_domains','sources','source_locations','record_sources','cases','case_links','analytes','labs','medications','monitoring','plan_items','questions','id_reservations'] LOOP
  EXECUTE format('SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),''[]''::jsonb) FROM __SCHEMA__.%I x',t) INTO rows;
  result:=result||jsonb_build_object(t,rows);
 END LOOP;
 RETURN result;
END $fn$;
CREATE FUNCTION __SCHEMA__.sha(value jsonb) RETURNS text LANGUAGE sql IMMUTABLE
SET search_path=pg_catalog,pg_temp AS $fn$ SELECT encode(sha256(convert_to(value::text,'UTF8')),'hex') $fn$;

CREATE FUNCTION __SCHEMA__.apply_delta(changes jsonb) RETURNS void
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
   ELSE NULL END;
  IF keys IS NULL OR action IS NULL OR action NOT IN ('INSERT','UPDATE','DELETE') THEN RAISE EXCEPTION 'unsupported table/action'; END IF;
  IF t='records' AND action IN ('INSERT','DELETE') THEN RAISE EXCEPTION 'REC allocation/purge requires separate protocol'; END IF;
  IF jsonb_typeof(delta->'key') IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(delta->'key'))<>cardinality(keys) THEN RAISE EXCEPTION 'exact key required'; END IF;
  predicate:='';
  FOREACH k IN ARRAY keys LOOP
   IF nullif(delta->'key'->>k,'') IS NULL THEN RAISE EXCEPTION 'missing key'; END IF;
   predicate:=predicate||CASE WHEN predicate='' THEN '' ELSE ' AND ' END||format('to_jsonb(x)->%L = $1->%L',k,k);
  END LOOP;
  EXECUTE format('SELECT to_jsonb(x) FROM __SCHEMA__.%I x WHERE %s FOR UPDATE',t,predicate) USING delta->'key' INTO current_row;
  IF action='INSERT' THEN
   IF current_row IS NOT NULL OR delta->>'expected_sha' IS NOT NULL THEN RAISE EXCEPTION 'insert conflict'; END IF;
  ELSE
   IF current_row IS NULL OR __SCHEMA__.sha(current_row) IS DISTINCT FROM delta->>'expected_sha' THEN RAISE EXCEPTION 'stale or missing row'; END IF;
  END IF;
  IF action='DELETE' THEN
   EXECUTE format('DELETE FROM __SCHEMA__.%I x WHERE %s',t,predicate) USING delta->'key';
  ELSE
   IF jsonb_typeof(data) IS DISTINCT FROM 'object' OR data='{}'::jsonb THEN RAISE EXCEPTION 'row fields required'; END IF;
   IF EXISTS(SELECT 1 FROM jsonb_object_keys(data) c WHERE NOT EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass('__SCHEMA__.'||t) AND a.attname=c AND a.attnum>0 AND NOT a.attisdropped)) THEN RAISE EXCEPTION 'unknown column'; END IF;
   FOREACH k IN ARRAY keys LOOP
    IF action='INSERT' AND data->k IS DISTINCT FROM delta->'key'->k THEN RAISE EXCEPTION 'insert key mismatch'; END IF;
    IF action='UPDATE' AND data ? k THEN RAISE EXCEPTION 'immutable key'; END IF;
   END LOOP;
   IF t='records' AND (data ? 'nnn' OR data ? 'record_date' OR data ? 'created_at') THEN RAISE EXCEPTION 'immutable REC identity'; END IF;
   cols:=''; sets:='';
   FOR col IN SELECT jsonb_object_keys(data) ORDER BY 1 LOOP
    cols:=cols||CASE WHEN cols='' THEN '' ELSE ',' END||quote_ident(col);
    sets:=sets||CASE WHEN sets='' THEN '' ELSE ',' END||format('%I=v.%I',col,col);
   END LOOP;
   IF action='INSERT' THEN
    EXECUTE format('INSERT INTO __SCHEMA__.%I (%s) OVERRIDING SYSTEM VALUE SELECT %s FROM jsonb_populate_record(NULL::__SCHEMA__.%I,$1) v',t,cols,cols,t) USING data;
   ELSE
    EXECUTE format('UPDATE __SCHEMA__.%I x SET %s FROM jsonb_populate_record(NULL::__SCHEMA__.%I,$2) v WHERE %s',t,sets,t,predicate) USING delta->'key',data;
   END IF;
  END IF;
  GET DIAGNOSTICS n=ROW_COUNT;
  IF n<>1 THEN RAISE EXCEPTION 'affected row count mismatch'; END IF;
 END LOOP;
END $fn$;

CREATE FUNCTION __SCHEMA__.publish(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE c __SCHEMA__.candidates%rowtype; before_state jsonb; after_state jsonb; op uuid; v_sha text;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO c FROM __SCHEMA__.candidates WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'candidate missing'; END IF;
 IF EXISTS(SELECT 1 FROM __SCHEMA__.publish_audit WHERE request_key=p_key) THEN
  IF c.candidate_sha IS DISTINCT FROM __SCHEMA__.sha(c.payload) OR c.candidate_sha IS DISTINCT FROM (SELECT a.candidate_sha FROM __SCHEMA__.publish_audit a WHERE a.request_key=p_key) THEN RAISE EXCEPTION 'idempotency payload conflict'; END IF;
  RETURN jsonb_build_object('state','FINALIZED','replayed',true,'test_only',true);
 END IF;
 IF c.approved IS NOT TRUE OR c.expires_at<=clock_timestamp() OR c.candidate_sha IS DISTINCT FROM __SCHEMA__.sha(c.payload) THEN RAISE EXCEPTION 'approval missing/expired/tampered'; END IF;
 -- Lock the fixture domain so non-protocol fixture writes cannot race this checkpoint.
 LOCK TABLE __SCHEMA__.records,__SCHEMA__.domains,__SCHEMA__.record_domains,__SCHEMA__.sources,__SCHEMA__.source_locations,__SCHEMA__.record_sources,__SCHEMA__.cases,__SCHEMA__.case_links,__SCHEMA__.analytes,__SCHEMA__.labs,__SCHEMA__.medications,__SCHEMA__.monitoring,__SCHEMA__.plan_items,__SCHEMA__.questions,__SCHEMA__.id_reservations IN SHARE ROW EXCLUSIVE MODE;
 before_state:=__SCHEMA__.checkpoint();
 IF __SCHEMA__.sha(before_state) IS DISTINCT FROM c.expected_before_sha THEN RAISE EXCEPTION 'stale domain snapshot'; END IF;
 INSERT INTO __SCHEMA__.operations(operation,mode,scope,state,notes) VALUES('SYNTHETIC_DELTA','maintenance',ARRAY[p_key],'PREPARED','synthetic approval/verifier only') RETURNING operation_id INTO op;
 PERFORM __SCHEMA__.apply_delta(c.payload->'changes');
 after_state:=__SCHEMA__.checkpoint();v_sha:=__SCHEMA__.sha(after_state);
 IF v_sha IS DISTINCT FROM c.expected_after_sha THEN RAISE EXCEPTION 'unexpected after snapshot'; END IF;
 IF (SELECT count(*) FROM __SCHEMA__.structural_checks())<>20 OR EXISTS(SELECT 1 FROM __SCHEMA__.structural_checks() WHERE passed IS DISTINCT FROM true) THEN RAISE EXCEPTION 'structural validation failed'; END IF;
 IF EXISTS(SELECT 1 FROM __SCHEMA__.record_domains d LEFT JOIN __SCHEMA__.records r ON r.record_id=d.record_id WHERE r.record_id IS NULL) OR EXISTS(SELECT 1 FROM __SCHEMA__.records r WHERE ARRAY(SELECT d.domain_code FROM __SCHEMA__.record_domains d WHERE d.record_id=r.record_id ORDER BY 1) IS DISTINCT FROM ARRAY(SELECT DISTINCT unnest(r.tags) ORDER BY 1)) THEN RAISE EXCEPTION 'domain representation mismatch'; END IF;
 IF EXISTS(SELECT 1 FROM __SCHEMA__.record_sources r LEFT JOIN __SCHEMA__.records x ON x.record_id=r.record_id LEFT JOIN __SCHEMA__.sources s ON s.source_id=r.source_id WHERE x.record_id IS NULL OR s.source_id IS NULL) OR EXISTS(SELECT 1 FROM __SCHEMA__.sources s WHERE s.sha256 IS NULL OR s.sha256 !~ '^[a-fA-F0-9]{64}$' OR s.size_bytes IS NULL OR s.size_bytes<0 OR (SELECT count(*) FROM __SCHEMA__.source_locations l WHERE l.source_id=s.source_id AND l.location_role='PRIMARY' AND l.verified_at IS NOT NULL)<>1) THEN RAISE EXCEPTION 'source binding invalid'; END IF;
 IF EXISTS(SELECT 1 FROM (SELECT basis_record_id FROM __SCHEMA__.medications UNION ALL SELECT basis_record_id FROM __SCHEMA__.monitoring UNION ALL SELECT basis_record_id FROM __SCHEMA__.plan_items UNION ALL SELECT basis_record_id FROM __SCHEMA__.questions) d WHERE d.basis_record_id IS NULL OR NOT EXISTS(SELECT 1 FROM __SCHEMA__.records r WHERE r.record_id=d.basis_record_id)) THEN RAISE EXCEPTION 'derived basis missing'; END IF;
 IF EXISTS(SELECT 1 FROM __SCHEMA__.medications m WHERE m.status='active' AND (m.metadata->>'intake_event' IS NULL OR (SELECT count(*) FROM __SCHEMA__.questions q WHERE q.status='open' AND q.basis_record_id=m.basis_record_id AND q.metadata->>'medication_id'=m.medication_id::text AND q.metadata->>'intake_event'=m.metadata->>'intake_event' AND q.metadata->>'check_kind'='drug_interactions')<>1)) THEN RAISE EXCEPTION 'interaction question missing or duplicated'; END IF;
 IF (SELECT count(*) FROM __SCHEMA__.semantic_receipts s WHERE s.request_key=p_key AND s.rule_id IN (19,20,21,22,27,28,29,30,31,37) AND s.status='PASS' AND s.candidate_sha=c.candidate_sha AND s.after_sha=v_sha AND s.checked_at>clock_timestamp()-interval '10 minutes' AND s.checked_at<=clock_timestamp() AND s.evidence_sha~'^[a-f0-9]{64}$' AND nullif(s.methodology,'') IS NOT NULL)<>10 THEN RAISE EXCEPTION 'semantic/source evidence missing or stale'; END IF;
 INSERT INTO __SCHEMA__.publish_audit VALUES(p_key,op,c.candidate_sha,before_state,after_state,c.expected_before_sha,v_sha);
 UPDATE __SCHEMA__.operations SET state='FINALIZED',result='success',finalized_at=clock_timestamp(),updated_at=clock_timestamp() WHERE operation_id=op;
 RETURN jsonb_build_object('state','FINALIZED','replayed',false,'test_only',true);
END $fn$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA __SCHEMA__ FROM PUBLIC;
