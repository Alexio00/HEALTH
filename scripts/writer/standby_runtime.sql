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
