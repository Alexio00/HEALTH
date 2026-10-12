-- Protected SQL upload journal; install after source_runtime.sql.
-- A trusted provisioner registers exact folders. Writer gets only these RPCs.
CREATE TABLE __SCHEMA__.upload_folders (
 folder text PRIMARY KEY CHECK(folder ~ '^[A-Za-z0-9_-]{8,128}$'),
 enabled boolean NOT NULL DEFAULT false
);
CREATE TABLE __SCHEMA__.source_upload_sessions (
 marker uuid PRIMARY KEY REFERENCES __SCHEMA__.source_uploads(marker),
 folder text NOT NULL REFERENCES __SCHEMA__.upload_folders(folder),
 state text NOT NULL CHECK(state IN ('PLANNED','STARTING','SESSION','COMPLETE')),
 session_uri text, object_id text, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK((state IN ('PLANNED','STARTING') AND session_uri IS NULL AND object_id IS NULL)
    OR (state='SESSION' AND session_uri IS NOT NULL AND object_id IS NULL)
    OR (state='COMPLETE' AND session_uri IS NOT NULL AND object_id IS NOT NULL))
);
ALTER TABLE __SCHEMA__.upload_folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE __SCHEMA__.source_upload_sessions ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION __SCHEMA__.upload_guard(p_marker uuid,p_active boolean,p_locked boolean)
RETURNS __SCHEMA__.source_uploads LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u __SCHEMA__.source_uploads%rowtype; operation_state text;
 key bigint:=hashtextextended(p_marker::text,63741020261012);
BEGIN
 SELECT x.* INTO u FROM __SCHEMA__.source_uploads x JOIN __SCHEMA__.prepared_requests p USING(request_key)
  WHERE x.marker=p_marker AND p.caller=session_user AND p.operation_id=x.operation_id;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='upload ownership denied'; END IF;
 SELECT state INTO operation_state FROM __SCHEMA__.operations WHERE operation_id=u.operation_id;
 IF p_active AND (operation_state IS DISTINCT FROM 'PREPARED' OR u.state NOT IN ('PLANNED','UNCERTAIN','VERIFIED')
  OR NOT EXISTS(SELECT 1 FROM __SCHEMA__.writer_intents i WHERE i.request_key=u.request_key
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

CREATE FUNCTION __SCHEMA__.upload_claim(p_marker uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM __SCHEMA__.upload_guard(p_marker,false,false);
 IF NOT pg_try_advisory_lock(63741020261013) THEN RETURN false; END IF;
 IF pg_try_advisory_lock(hashtextextended(p_marker::text,63741020261012)) THEN RETURN true; END IF;
 PERFORM pg_advisory_unlock(63741020261013); RETURN false;
END $fn$;
CREATE FUNCTION __SCHEMA__.upload_release(p_marker uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM __SCHEMA__.upload_guard(p_marker,false,true);
 IF NOT pg_advisory_unlock(hashtextextended(p_marker::text,63741020261012)) THEN RETURN false; END IF;
 RETURN pg_advisory_unlock(63741020261013);
END $fn$;
CREATE FUNCTION __SCHEMA__.upload_get(p_marker uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u __SCHEMA__.source_uploads%rowtype; j __SCHEMA__.source_upload_sessions%rowtype;
BEGIN
 u:=__SCHEMA__.upload_guard(p_marker,false,false);
 SELECT * INTO j FROM __SCHEMA__.source_upload_sessions WHERE marker=p_marker;
 IF NOT FOUND THEN RETURN NULL; END IF;
 RETURN jsonb_build_object('marker',p_marker,'folder',j.folder,'source_id',u.source_id,
  'sha256',u.source_row->>'sha256','size_bytes',(u.source_row->>'size_bytes')::bigint,
  'session_uri',j.session_uri,'object_id',j.object_id,'state',j.state);
END $fn$;
CREATE FUNCTION __SCHEMA__.upload_plan(p_marker uuid,p_folder text,p_source text,p_sha text,p_size bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u __SCHEMA__.source_uploads%rowtype; j __SCHEMA__.source_upload_sessions%rowtype;
BEGIN
 u:=__SCHEMA__.upload_guard(p_marker,false,true);
 IF p_source IS DISTINCT FROM u.source_id OR p_sha IS DISTINCT FROM u.source_row->>'sha256'
  OR p_size IS DISTINCT FROM (u.source_row->>'size_bytes')::bigint OR p_size<=0 OR p_size>1073741824
  OR u.provider IS DISTINCT FROM 'gdrive' THEN RAISE EXCEPTION 'upload Source binding conflict'; END IF;
 SELECT * INTO j FROM __SCHEMA__.source_upload_sessions WHERE marker=p_marker FOR UPDATE;
 IF FOUND THEN
  IF j.folder IS DISTINCT FROM p_folder THEN RAISE EXCEPTION 'upload folder binding conflict'; END IF;
  IF j.state<>'COMPLETE' THEN PERFORM __SCHEMA__.upload_guard(p_marker,true,true); END IF;
 ELSE
  PERFORM __SCHEMA__.upload_guard(p_marker,true,true);
  IF NOT EXISTS(SELECT 1 FROM __SCHEMA__.upload_folders WHERE folder=p_folder AND enabled)
   THEN RAISE EXCEPTION 'registered upload folder required'; END IF;
  INSERT INTO __SCHEMA__.source_upload_sessions(marker,folder,state) VALUES(p_marker,p_folder,'PLANNED');
 END IF;
 RETURN __SCHEMA__.upload_get(p_marker);
END $fn$;
CREATE FUNCTION __SCHEMA__.upload_authorize(p_marker uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM __SCHEMA__.upload_guard(p_marker,true,true);
 IF NOT EXISTS(SELECT 1 FROM __SCHEMA__.source_upload_sessions j
   JOIN __SCHEMA__.upload_folders f USING(folder) WHERE j.marker=p_marker AND f.enabled
    AND j.state IN ('STARTING','SESSION'))
 THEN RAISE EXCEPTION 'authorized active upload session required'; END IF;
END $fn$;
CREATE FUNCTION __SCHEMA__.upload_description(p_marker uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE u __SCHEMA__.source_uploads%rowtype;
BEGIN
 u:=__SCHEMA__.upload_guard(p_marker,true,true);
 RETURN u.source_row;
END $fn$;
CREATE FUNCTION __SCHEMA__.upload_starting(p_marker uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 PERFORM __SCHEMA__.upload_guard(p_marker,true,true);
 UPDATE __SCHEMA__.source_upload_sessions j SET state='STARTING'
  WHERE marker=p_marker AND state='PLANNED'
   AND EXISTS(SELECT 1 FROM __SCHEMA__.upload_folders f WHERE f.folder=j.folder AND f.enabled);
 IF NOT FOUND THEN RAISE EXCEPTION 'upload initiation outcome uncertain or folder disabled'; END IF;
END $fn$;
CREATE FUNCTION __SCHEMA__.upload_session(p_marker uuid,p_uri text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 -- Save an already received provider reply even if approval expires meanwhile.
 -- No HTTP request is made here; upload_authorize guards each external request.
 PERFORM __SCHEMA__.upload_guard(p_marker,false,true);
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
 UPDATE __SCHEMA__.source_upload_sessions SET state='SESSION',session_uri=p_uri
  WHERE marker=p_marker AND state='STARTING';
 IF NOT FOUND THEN RAISE EXCEPTION 'upload session transition rejected'; END IF;
END $fn$;
CREATE FUNCTION __SCHEMA__.upload_complete(p_marker uuid,p_object text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE j __SCHEMA__.source_upload_sessions%rowtype;
BEGIN
 PERFORM __SCHEMA__.upload_guard(p_marker,false,true);
 SELECT * INTO j FROM __SCHEMA__.source_upload_sessions WHERE marker=p_marker FOR UPDATE;
 IF NOT FOUND OR p_object IS NULL OR p_object !~ '^[A-Za-z0-9_-]{8,128}$'
  OR j.state NOT IN ('SESSION','COMPLETE') OR (j.object_id IS NOT NULL AND j.object_id IS DISTINCT FROM p_object)
 THEN RAISE EXCEPTION 'upload object binding conflict'; END IF;
 IF j.state='COMPLETE' THEN RETURN; END IF;
 UPDATE __SCHEMA__.source_upload_sessions SET state='COMPLETE',object_id=p_object WHERE marker=p_marker;
 -- COMPLETE is a transport fact only. It does not attest bytes or publish Source.
END $fn$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA __SCHEMA__ FROM PUBLIC;
GRANT EXECUTE ON FUNCTION __SCHEMA__.upload_claim(uuid),__SCHEMA__.upload_release(uuid),
 __SCHEMA__.upload_get(uuid),__SCHEMA__.upload_plan(uuid,text,text,text,bigint),
 __SCHEMA__.upload_authorize(uuid),
 __SCHEMA__.upload_description(uuid),
 __SCHEMA__.upload_starting(uuid),__SCHEMA__.upload_session(uuid,text),
 __SCHEMA__.upload_complete(uuid,text) TO health_test_writer_role;
