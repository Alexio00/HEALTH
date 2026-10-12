-- TEST-only authorization bridge. Verified JWT claims arrive from a separate
-- trusted principal, never the normal writer. Semantic receipts are separate.
CREATE TABLE __SCHEMA__.approval_policy (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 principal name NOT NULL, actor_id text NOT NULL, repository_id text NOT NULL,
 workflow_sha text NOT NULL CHECK(workflow_sha ~ '^[a-f0-9]{40}$')
);
CREATE TABLE __SCHEMA__.approval_receipts (
 request_key text NOT NULL, kind text NOT NULL CHECK(kind IN ('intent','candidate')),
 digest text NOT NULL, actor_id text NOT NULL, workflow_sha text NOT NULL,
 token_jti text NOT NULL, run_id text NOT NULL, run_attempt text NOT NULL,
 accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(request_key,kind), UNIQUE(token_jti,kind)
);
ALTER TABLE __SCHEMA__.approval_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE __SCHEMA__.approval_receipts ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION __SCHEMA__.accept_authorization(p_key text,p_kind text,p_digest text,p_actor text,
 p_repo text,p_workflow_sha text,p_jti text,p_run text,p_attempt text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE policy __SCHEMA__.approval_policy%rowtype; receipt __SCHEMA__.approval_receipts%rowtype;
 i __SCHEMA__.writer_intents%rowtype; c __SCHEMA__.candidates%rowtype;
BEGIN
 SELECT * INTO policy FROM __SCHEMA__.approval_policy WHERE singleton;
 IF policy.principal IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='trusted authorization bridge required'; END IF;
 IF policy.actor_id IS DISTINCT FROM p_actor OR policy.repository_id IS DISTINCT FROM p_repo
  OR policy.workflow_sha IS DISTINCT FROM p_workflow_sha OR p_kind IS NULL OR p_kind NOT IN ('intent','candidate')
  OR p_digest IS NULL OR p_digest !~ '^[a-f0-9]{64}$' OR p_jti IS NULL OR length(p_jti)<8 OR length(p_jti)>256
  OR p_run IS NULL OR p_run !~ '^[0-9]{1,20}$' OR p_attempt IS NULL OR p_attempt !~ '^[0-9]{1,6}$'
  THEN RAISE EXCEPTION 'authorization identity/pin mismatch'; END IF;
 PERFORM pg_advisory_xact_lock(63741020261011);
 SELECT * INTO i FROM __SCHEMA__.writer_intents WHERE request_key=p_key FOR UPDATE;
 IF NOT FOUND OR i.intent_sha IS DISTINCT FROM __SCHEMA__.sha(i.intent) OR i.expires_at<=clock_timestamp()
  THEN RAISE EXCEPTION 'intent missing/changed/expired'; END IF;
 IF p_kind='candidate' THEN
  SELECT * INTO c FROM __SCHEMA__.candidates WHERE request_key=p_key FOR UPDATE;
  IF NOT FOUND OR i.approved IS NOT TRUE OR c.expires_at<=clock_timestamp()
   OR c.candidate_sha IS DISTINCT FROM __SCHEMA__.sha(c.payload) OR c.candidate_sha IS DISTINCT FROM p_digest
   OR c.payload->>'intent_sha' IS DISTINCT FROM i.intent_sha THEN RAISE EXCEPTION 'exact candidate binding conflict'; END IF;
 ELSIF i.intent_sha IS DISTINCT FROM p_digest THEN RAISE EXCEPTION 'exact intent binding conflict'; END IF;
 SELECT * INTO receipt FROM __SCHEMA__.approval_receipts WHERE request_key=p_key AND kind=p_kind;
 IF FOUND THEN
  IF receipt.digest IS DISTINCT FROM p_digest OR receipt.workflow_sha IS DISTINCT FROM p_workflow_sha
   THEN RAISE EXCEPTION 'approval replay binding conflict'; END IF;
  IF (p_kind='intent' AND i.approved IS NOT TRUE) OR (p_kind='candidate' AND c.approved IS NOT TRUE)
   THEN RAISE EXCEPTION 'approval revoked'; END IF;
  RETURN jsonb_build_object('accepted',true,'replayed',true,'digest',p_digest,'test_only',true);
 END IF;
 INSERT INTO __SCHEMA__.approval_receipts(request_key,kind,digest,actor_id,workflow_sha,token_jti,run_id,run_attempt)
  VALUES(p_key,p_kind,p_digest,p_actor,p_workflow_sha,p_jti,p_run,p_attempt);
 IF p_kind='intent' THEN UPDATE __SCHEMA__.writer_intents SET approved=true WHERE request_key=p_key;
 ELSE UPDATE __SCHEMA__.candidates SET approved=true WHERE request_key=p_key; END IF;
 RETURN jsonb_build_object('accepted',true,'replayed',false,'digest',p_digest,'test_only',true);
END $fn$;
CREATE FUNCTION __SCHEMA__.authorization_request(p_key text,p_kind text) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE i __SCHEMA__.writer_intents%rowtype; digest text;
BEGIN
 SELECT * INTO i FROM __SCHEMA__.writer_intents WHERE request_key=p_key;
 IF NOT FOUND OR i.caller IS DISTINCT FROM session_user THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='request ownership denied'; END IF;
 IF p_kind='intent' THEN digest:=i.intent_sha;
 ELSIF p_kind='candidate' THEN SELECT candidate_sha INTO digest FROM __SCHEMA__.candidates WHERE request_key=p_key;
 ELSE RAISE EXCEPTION 'invalid authorization kind'; END IF;
 IF digest IS NULL THEN RAISE EXCEPTION 'authorization target missing'; END IF;
 RETURN jsonb_build_object('request_key',p_key,'kind',p_kind,'digest',digest,'test_only',true);
END $fn$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA __SCHEMA__ FROM PUBLIC;
GRANT EXECUTE ON FUNCTION __SCHEMA__.authorization_request(text,text) TO health_test_writer_role;
