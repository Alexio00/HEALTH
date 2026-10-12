-- Fixed private destination, callable only through the server authorization
-- role. No Writer login, anonymous or authenticated client can invoke it.
CREATE FUNCTION public.__CANONICAL_RPC__(p_key text,p_kind text,p_digest text,p_actor text,
 p_repo text,p_workflow_sha text,p_jti text,p_run text,p_attempt text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE claims jsonb;
BEGIN
 claims:=coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb;
 IF session_user<>'authenticator' OR claims->>'role' IS DISTINCT FROM 'service_role' THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='server-only authorization bridge required'; END IF;
 IF p_key IS NULL OR p_key !~ '^writer-[a-f0-9]{32}$' THEN RAISE EXCEPTION 'opaque request identity required'; END IF;
 PERFORM __CANONICAL_SCHEMA__.require_enabled();
 RETURN __CANONICAL_SCHEMA__.accept_authorization(p_key,p_kind,p_digest,p_actor,p_repo,p_workflow_sha,p_jti,p_run,p_attempt);
END $fn$;
REVOKE ALL ON FUNCTION public.__CANONICAL_RPC__(text,text,text,text,text,text,text,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.__CANONICAL_RPC__(text,text,text,text,text,text,text,text,text) TO service_role;
