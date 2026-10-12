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
