-- Disposable TEST-only REST bridge for the rendered private fixture. Never a
-- migration of clinical public tables. service_role is held by the broker only.
BEGIN;
CREATE FUNCTION public.health_test_authorize_writer_v3(p_schema text,p_key text,p_kind text,p_digest text,
 p_actor text,p_repo text,p_workflow_sha text,p_jti text,p_run text,p_attempt text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE result jsonb; claims jsonb;
BEGIN
 claims:=coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
 IF session_user<>'authenticator' OR claims->>'role' IS DISTINCT FROM 'service_role' THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='server-only authorization bridge required'; END IF;
 IF p_schema IS DISTINCT FROM '__FIXTURE_SCHEMA__' OR p_schema !~ '^health_writer_fixture_[a-f0-9]{12}$'
  OR (SELECT obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname=p_schema)
   IS DISTINCT FROM 'HEALTH_SYNTHETIC_WRITER_FIXTURE_V1' THEN RAISE EXCEPTION 'exact TEST fixture required'; END IF;
 EXECUTE format('SELECT %I.accept_authorization($1,$2,$3,$4,$5,$6,$7,$8,$9)',p_schema)
 INTO result USING p_key,p_kind,p_digest,p_actor,p_repo,p_workflow_sha,p_jti,p_run,p_attempt;
 RETURN result;
END $fn$;
REVOKE ALL ON FUNCTION public.health_test_authorize_writer_v3(text,text,text,text,text,text,text,text,text,text) FROM PUBLIC,anon,authenticated,health_test_ci;
GRANT EXECUTE ON FUNCTION public.health_test_authorize_writer_v3(text,text,text,text,text,text,text,text,text,text) TO service_role;
COMMIT;
