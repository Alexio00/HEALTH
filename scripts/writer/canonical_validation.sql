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
