-- Optional TEST-only overlay. No production migration, Auth or owner verifier.
-- Trusted administrator provisions intents and exact candidate approvals.
CREATE TABLE __SCHEMA__.writer_intents (
 request_key text PRIMARY KEY, caller name NOT NULL, intent jsonb NOT NULL,
 intent_sha text NOT NULL CHECK(intent_sha ~ '^[a-f0-9]{64}$'),
 approved boolean NOT NULL DEFAULT false, expires_at timestamptz NOT NULL
);
CREATE TABLE __SCHEMA__.prepared_requests (
 request_key text PRIMARY KEY REFERENCES __SCHEMA__.writer_intents(request_key),
 operation_id uuid UNIQUE NOT NULL REFERENCES __SCHEMA__.operations(operation_id),
 caller name NOT NULL, intent_sha text NOT NULL,
 operation_class text NOT NULL CHECK(operation_class='SYNTHETIC_DURABLE_DELTA'),
 proposed_record_id text, nnn integer, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE __SCHEMA__.writer_validation_results (
 operation_id uuid REFERENCES __SCHEMA__.operations(operation_id), rule_id integer,
 status text NOT NULL CHECK(status='PASS'), candidate_sha text NOT NULL,
 after_sha text NOT NULL, checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(operation_id,rule_id)
);
ALTER TABLE __SCHEMA__.writer_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE __SCHEMA__.prepared_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE __SCHEMA__.writer_validation_results ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION __SCHEMA__.prepare(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE i __SCHEMA__.writer_intents%rowtype; p __SCHEMA__.prepared_requests%rowtype;
 op uuid; number integer; rec text; day date;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO i FROM __SCHEMA__.writer_intents WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR i.caller IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 IF i.intent_sha IS DISTINCT FROM __SCHEMA__.sha(i.intent) THEN RAISE EXCEPTION 'intent digest conflict'; END IF;
 SELECT * INTO p FROM __SCHEMA__.prepared_requests WHERE request_key=p_key;
 IF FOUND THEN
  IF p.intent_sha IS DISTINCT FROM i.intent_sha OR p.caller IS DISTINCT FROM session_user THEN RAISE EXCEPTION 'prepared request conflict'; END IF;
  RETURN __SCHEMA__.request_status(p_key);
 END IF;
 IF i.approved IS NOT TRUE OR i.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'intent approval missing/expired'; END IF;
 IF jsonb_typeof(i.intent) IS DISTINCT FROM 'object'
  OR i.intent->>'action' IS NULL OR i.intent->>'action' NOT IN ('CREATE_REC','UPDATE')
  OR EXISTS(SELECT 1 FROM jsonb_object_keys(i.intent) k WHERE k NOT IN ('action','record_date'))
  THEN RAISE EXCEPTION 'invalid intent'; END IF;
 INSERT INTO __SCHEMA__.operations(operation,mode,scope,state,notes)
  VALUES('SYNTHETIC_DURABLE_DELTA','maintenance',ARRAY[p_key],'PREPARED','synthetic intent and candidate approval only') RETURNING operation_id INTO op;
 IF i.intent->>'action'='CREATE_REC' THEN
  day:=(i.intent->>'record_date')::date;
  IF day IS NULL OR day::text IS DISTINCT FROM i.intent->>'record_date' THEN RAISE EXCEPTION 'exact record date required'; END IF;
  SELECT coalesce(max(n),0)+1 INTO number FROM (
   SELECT nnn n FROM __SCHEMA__.id_reservations UNION ALL SELECT nnn FROM __SCHEMA__.records) x;
  IF number>999 THEN RAISE EXCEPTION 'NNN exhausted'; END IF;
  rec:='REC-'||to_char(day,'YYYYMMDD')||'-'||lpad(number::text,3,'0');
  INSERT INTO __SCHEMA__.id_reservations(nnn,state,operation_id,reserved_at,metadata)
   VALUES(number,'reserved',op,clock_timestamp(),jsonb_build_object('proposed_record_id',rec,'record_date',day::text));
 END IF;
 INSERT INTO __SCHEMA__.prepared_requests VALUES(p_key,op,session_user,i.intent_sha,'SYNTHETIC_DURABLE_DELTA',rec,number,clock_timestamp());
 RETURN __SCHEMA__.request_status(p_key);
END $fn$;

CREATE FUNCTION __SCHEMA__.request_status(p_key text) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p __SCHEMA__.prepared_requests%rowtype; state text; digest text;
BEGIN
 SELECT * INTO p FROM __SCHEMA__.prepared_requests WHERE request_key=p_key;
 IF NOT FOUND THEN
  IF NOT EXISTS(SELECT 1 FROM __SCHEMA__.writer_intents WHERE request_key=p_key AND caller=session_user)
   THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
  RETURN jsonb_build_object('state','NOT_PREPARED','test_only',true);
 END IF;
 IF p.caller IS DISTINCT FROM session_user THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT o.state INTO state FROM __SCHEMA__.operations o WHERE operation_id=p.operation_id;
 SELECT candidate_sha INTO digest FROM __SCHEMA__.publish_audit WHERE request_key=p_key;
 RETURN jsonb_build_object('state',state,'operation_id',p.operation_id,'record_id',p.proposed_record_id,'nnn',p.nnn,'candidate_sha',digest,'test_only',true);
END $fn$;

CREATE FUNCTION __SCHEMA__.finalize(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p __SCHEMA__.prepared_requests%rowtype; i __SCHEMA__.writer_intents%rowtype;
 c __SCHEMA__.candidates%rowtype; result jsonb; a __SCHEMA__.publish_audit%rowtype;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO p FROM __SCHEMA__.prepared_requests WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR p.caller IS DISTINCT FROM session_user THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT * INTO i FROM __SCHEMA__.writer_intents WHERE request_key=p_key FOR UPDATE;
 SELECT * INTO c FROM __SCHEMA__.candidates WHERE request_key=p_key FOR UPDATE;
 IF p.operation_class<>'SYNTHETIC_DURABLE_DELTA' OR i.caller IS DISTINCT FROM p.caller
  OR i.intent_sha IS DISTINCT FROM p.intent_sha OR i.intent_sha IS DISTINCT FROM __SCHEMA__.sha(i.intent)
  THEN RAISE EXCEPTION 'prepared request binding conflict'; END IF;
 IF EXISTS(SELECT 1 FROM __SCHEMA__.publish_audit WHERE request_key=p_key) THEN
  SELECT * INTO a FROM __SCHEMA__.publish_audit WHERE request_key=p_key;
  IF a.operation_id IS DISTINCT FROM p.operation_id THEN RAISE EXCEPTION 'audit operation conflict'; END IF;
  RETURN __SCHEMA__.publish_internal(p_key,p.operation_id);
 END IF;
 IF i.approved IS NOT TRUE OR i.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'intent approval missing/expired'; END IF;
 IF c.payload->>'intent_sha' IS DISTINCT FROM p.intent_sha THEN RAISE EXCEPTION 'candidate intent binding missing'; END IF;
 IF p.nnn IS NULL AND EXISTS(SELECT 1 FROM jsonb_array_elements(c.payload->'changes') d WHERE d->>'table'='records' AND d->>'action'='INSERT')
  THEN RAISE EXCEPTION 'unexpected REC allocation'; END IF;
 result:=__SCHEMA__.publish_internal(p_key,p.operation_id);
 IF i.expires_at<=clock_timestamp() THEN RAISE EXCEPTION 'intent approval expired during publication'; END IF;
 SELECT * INTO a FROM __SCHEMA__.publish_audit WHERE request_key=p_key;
 INSERT INTO __SCHEMA__.writer_validation_results
  SELECT p.operation_id,rule_id,'PASS',a.candidate_sha,a.after_sha,clock_timestamp() FROM __SCHEMA__.structural_checks()
  UNION ALL
  SELECT p.operation_id,rule_id,'PASS',a.candidate_sha,a.after_sha,clock_timestamp()
   FROM __SCHEMA__.semantic_receipts WHERE request_key=p_key AND rule_id IN (19,20,21,22,27,28,29,30,31,37);
 RETURN result;
END $fn$;

CREATE FUNCTION __SCHEMA__.abandon(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p __SCHEMA__.prepared_requests%rowtype; op_state text;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO p FROM __SCHEMA__.prepared_requests WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR p.caller IS DISTINCT FROM session_user THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT o.state INTO op_state FROM __SCHEMA__.operations o WHERE operation_id=p.operation_id
  AND operation='SYNTHETIC_DURABLE_DELTA' AND scope=ARRAY[p_key] FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'foreign operation or operation class'; END IF;
 IF op_state='FAILED' THEN RETURN __SCHEMA__.request_status(p_key); END IF;
 IF op_state IS DISTINCT FROM 'PREPARED' OR EXISTS(SELECT 1 FROM __SCHEMA__.publish_audit WHERE request_key=p_key)
  THEN RAISE EXCEPTION 'published or uncertain operation cannot be abandoned'; END IF;
 UPDATE __SCHEMA__.id_reservations SET state='retired',updated_at=clock_timestamp() WHERE operation_id=p.operation_id AND state='reserved';
 UPDATE __SCHEMA__.operations SET state='FAILED',result='abandoned',updated_at=clock_timestamp() WHERE operation_id=p.operation_id;
 RETURN __SCHEMA__.request_status(p_key);
END $fn$;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA __SCHEMA__ FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION __SCHEMA__.publish(text),__SCHEMA__.status(text) FROM health_test_writer_role;
GRANT EXECUTE ON FUNCTION __SCHEMA__.prepare(text),__SCHEMA__.finalize(text),__SCHEMA__.request_status(text),__SCHEMA__.abandon(text) TO health_test_writer_role;
