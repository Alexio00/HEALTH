-- Optional disposable TEST integration; install after durable_runtime.sql.
-- Separate verifier login attests actual adapter bytes. No production deployment.
CREATE TABLE __SCHEMA__.source_verifier_principals (principal name PRIMARY KEY);
CREATE TABLE __SCHEMA__.source_uploads (
 request_key text REFERENCES __SCHEMA__.prepared_requests(request_key),
 operation_id uuid NOT NULL REFERENCES __SCHEMA__.operations(operation_id),
 source_id text NOT NULL UNIQUE, marker uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
 source_row jsonb NOT NULL, provider text NOT NULL, account_alias text NOT NULL,
 state text NOT NULL DEFAULT 'PLANNED' CHECK(state IN ('PLANNED','UNCERTAIN','VERIFIED','BLOCKED','PUBLISHED')),
 object_id text, candidate_sha text, verifier name, checked_at timestamptz, safe_error text,
 PRIMARY KEY(request_key,source_id)
);
ALTER TABLE __SCHEMA__.source_verifier_principals ENABLE ROW LEVEL SECURITY;
ALTER TABLE __SCHEMA__.source_uploads ENABLE ROW LEVEL SECURITY;
CREATE UNIQUE INDEX source_upload_logical_path_unique ON __SCHEMA__.source_uploads ((source_row->>'logical_path'));

CREATE FUNCTION __SCHEMA__.plan_source(p_key text,p_source jsonb,p_provider text,p_account text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE p __SCHEMA__.prepared_requests%rowtype; u __SCHEMA__.source_uploads%rowtype;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO p FROM __SCHEMA__.prepared_requests WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR p.caller IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 IF (SELECT state FROM __SCHEMA__.operations WHERE operation_id=p.operation_id) IS DISTINCT FROM 'PREPARED'
  THEN RAISE EXCEPTION 'operation not prepared'; END IF;
 IF jsonb_typeof(p_source) IS DISTINCT FROM 'object'
  OR p_source->>'source_id' IS NULL OR (p_source->>'source_id') !~ '^SRC-[0-9]{8}-[0-9]{3,}$'
  OR p_source->>'sha256' IS NULL OR (p_source->>'sha256') !~ '^[a-f0-9]{64}$'
  OR jsonb_typeof(p_source->'size_bytes') IS DISTINCT FROM 'number'
  OR (p_source->>'size_bytes') !~ '^[0-9]+$'
  OR nullif(p_source->>'logical_path','') IS NULL OR nullif(p_source->>'original_filename','') IS NULL
  OR p_provider IS NULL OR p_provider NOT IN ('LOCAL_TEST','gdrive')
  OR p_account IS NULL OR p_account !~ '^[a-z0-9_-]{1,64}$'
  OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_source) k WHERE k NOT IN
    ('source_id','logical_path','original_filename','mime_type','size_bytes','sha256','source_date','metadata','created_at'))
  THEN RAISE EXCEPTION 'invalid Source plan'; END IF;
 PERFORM (p_source->>'size_bytes')::bigint;
 SELECT * INTO u FROM __SCHEMA__.source_uploads WHERE request_key=p_key AND source_id=p_source->>'source_id';
 IF FOUND THEN
  IF u.source_row IS DISTINCT FROM p_source OR u.provider IS DISTINCT FROM p_provider OR u.account_alias IS DISTINCT FROM p_account
   OR u.operation_id IS DISTINCT FROM p.operation_id THEN RAISE EXCEPTION 'Source plan replay conflict'; END IF;
 ELSE
  IF EXISTS(SELECT 1 FROM __SCHEMA__.sources WHERE source_id=p_source->>'source_id' OR logical_path=p_source->>'logical_path')
   THEN RAISE EXCEPTION 'existing Source identity/path'; END IF;
  INSERT INTO __SCHEMA__.source_uploads(request_key,operation_id,source_id,source_row,provider,account_alias)
   VALUES(p_key,p.operation_id,p_source->>'source_id',p_source,p_provider,p_account);
 END IF;
 RETURN __SCHEMA__.source_status(p_key,p_source->>'source_id');
END $fn$;

CREATE FUNCTION __SCHEMA__.source_status(p_key text,p_source text) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u __SCHEMA__.source_uploads%rowtype;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM __SCHEMA__.prepared_requests WHERE request_key=p_key AND caller=session_user)
  THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT * INTO u FROM __SCHEMA__.source_uploads WHERE request_key=p_key AND source_id=p_source;
 IF NOT FOUND THEN RAISE EXCEPTION 'Source plan missing'; END IF;
 RETURN jsonb_build_object('operation_id',u.operation_id,'source_id',u.source_id,'marker',u.marker,
  'state',u.state,'object_id',u.object_id,'candidate_sha',u.candidate_sha,'safe_error',u.safe_error,'test_only',true);
END $fn$;

CREATE FUNCTION __SCHEMA__.source_uncertain(p_key text,p_source text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 PERFORM __SCHEMA__.source_status(p_key,p_source);
 IF (SELECT o.state FROM __SCHEMA__.operations o JOIN __SCHEMA__.prepared_requests p USING(operation_id)
  WHERE p.request_key=p_key) IS DISTINCT FROM 'PREPARED' THEN RAISE EXCEPTION 'operation not prepared'; END IF;
 UPDATE __SCHEMA__.source_uploads SET state='UNCERTAIN' WHERE request_key=p_key AND source_id=p_source AND state='PLANNED';
 IF (SELECT state FROM __SCHEMA__.source_uploads WHERE request_key=p_key AND source_id=p_source) NOT IN ('UNCERTAIN','VERIFIED')
  THEN RAISE EXCEPTION 'upload cannot be retried'; END IF;
 RETURN __SCHEMA__.source_status(p_key,p_source);
END $fn$;

CREATE FUNCTION __SCHEMA__.begin_source_check(p_key text,p_source text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM __SCHEMA__.source_verifier_principals WHERE principal=session_user)
  THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='independent verifier required'; END IF;
 PERFORM pg_advisory_xact_lock(63741020261011);
 IF NOT EXISTS(SELECT 1 FROM __SCHEMA__.source_uploads u JOIN __SCHEMA__.operations o USING(operation_id)
  WHERE u.request_key=p_key AND u.source_id=p_source AND u.state IN ('UNCERTAIN','VERIFIED') AND o.state='PREPARED')
  THEN RAISE EXCEPTION 'Source not eligible for verification'; END IF;
 -- Invalidate the old receipt BEFORE the external read. A failed read must not
 -- leave a previously valid receipt available for publication.
 UPDATE __SCHEMA__.source_uploads SET state='UNCERTAIN',candidate_sha=NULL,verifier=NULL,checked_at=NULL
  WHERE request_key=p_key AND source_id=p_source;
END $fn$;

CREATE FUNCTION __SCHEMA__.attest_source(p_key text,p_source text,p_marker uuid,p_object text,p_sha text,p_size bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u __SCHEMA__.source_uploads%rowtype; c __SCHEMA__.candidates%rowtype; m jsonb;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM __SCHEMA__.source_verifier_principals WHERE principal=session_user)
  THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='independent verifier required'; END IF;
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO u FROM __SCHEMA__.source_uploads WHERE request_key=p_key AND source_id=p_source FOR UPDATE;
 SELECT * INTO c FROM __SCHEMA__.candidates WHERE request_key=p_key FOR UPDATE;
 IF u.marker IS DISTINCT FROM p_marker OR u.state NOT IN ('UNCERTAIN','VERIFIED')
  OR (SELECT state FROM __SCHEMA__.operations WHERE operation_id=u.operation_id) IS DISTINCT FROM 'PREPARED'
  OR c.candidate_sha IS NULL OR c.candidate_sha IS DISTINCT FROM __SCHEMA__.sha(c.payload)
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
  UPDATE __SCHEMA__.source_uploads SET state='BLOCKED',safe_error='source_digest_or_length_mismatch'
   WHERE request_key=p_key AND source_id=p_source;
  RETURN jsonb_build_object('state','BLOCKED','test_only',true);
 END IF;
 UPDATE __SCHEMA__.source_uploads SET state='VERIFIED',object_id=p_object,candidate_sha=c.candidate_sha,
  verifier=session_user,checked_at=clock_timestamp(),safe_error=NULL WHERE request_key=p_key AND source_id=p_source;
 RETURN jsonb_build_object('state','VERIFIED','test_only',true);
END $fn$;

ALTER FUNCTION __SCHEMA__.finalize(text) RENAME TO finalize_delta;
REVOKE EXECUTE ON FUNCTION __SCHEMA__.finalize_delta(text) FROM health_test_writer_role;
CREATE FUNCTION __SCHEMA__.finalize(p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE c __SCHEMA__.candidates%rowtype; p __SCHEMA__.prepared_requests%rowtype;
 u __SCHEMA__.source_uploads%rowtype; m jsonb; result jsonb;
BEGIN
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO p FROM __SCHEMA__.prepared_requests WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR p.caller IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 SELECT * INTO c FROM __SCHEMA__.candidates WHERE request_key=p_key FOR UPDATE;
 IF EXISTS(SELECT 1 FROM __SCHEMA__.publish_audit WHERE request_key=p_key) THEN RETURN __SCHEMA__.finalize_delta(p_key); END IF;
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
   SELECT * INTO u FROM __SCHEMA__.source_uploads WHERE request_key=p_key AND source_id=m->>'source_id' FOR UPDATE;
   IF NOT FOUND OR u.operation_id IS DISTINCT FROM p.operation_id OR u.state IS DISTINCT FROM 'VERIFIED'
    OR u.candidate_sha IS DISTINCT FROM c.candidate_sha OR u.marker::text IS DISTINCT FROM m->>'marker'
    OR u.object_id IS DISTINCT FROM m->>'object_id' OR u.source_row IS DISTINCT FROM m->'source_row'
    OR u.provider IS DISTINCT FROM m->>'provider' OR u.account_alias IS DISTINCT FROM m->>'account_alias'
    OR u.checked_at IS NULL OR u.checked_at<clock_timestamp()-interval '10 minutes' OR u.checked_at>clock_timestamp()
    OR NOT EXISTS(SELECT 1 FROM __SCHEMA__.source_verifier_principals WHERE principal=u.verifier)
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
 result:=__SCHEMA__.finalize_delta(p_key);
 UPDATE __SCHEMA__.source_uploads SET state='PUBLISHED' WHERE request_key=p_key AND state='VERIFIED';
 RETURN result;
END $fn$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA __SCHEMA__ FROM PUBLIC;
GRANT EXECUTE ON FUNCTION __SCHEMA__.plan_source(text,jsonb,text,text),__SCHEMA__.source_status(text,text),
 __SCHEMA__.source_uncertain(text,text),__SCHEMA__.finalize(text) TO health_test_writer_role;
-- Administrator grants only attest_source + schema USAGE to a separate verifier.
