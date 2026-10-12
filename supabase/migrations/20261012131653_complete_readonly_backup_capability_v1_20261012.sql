-- Fixed capability for full backup capture, without clinical/control DML.
-- Provision NOLOGIN first. A separate private credential step sets SCRAM/Login.
-- Apply only through an exact-project, reviewed owner connection.
BEGIN;
DO $preflight$
BEGIN
 IF current_database()<>'postgres' OR current_user<>'postgres' THEN
  RAISE EXCEPTION 'reviewed owner database identity required'; END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='health_backup_reader') OR
    EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='health_backup_control') THEN
  RAISE EXCEPTION 'backup reader already exists; exact reconciliation required'; END IF;
 IF EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname NOT IN ('pg_catalog','information_schema')
   AND has_schema_privilege('public',n.oid,'USAGE')
   AND p.prosecdef AND has_function_privilege('public',p.oid,'EXECUTE')) THEN
  RAISE EXCEPTION 'public privileged entrypoint requires separate privilege review'; END IF;
END $preflight$;
CREATE ROLE health_backup_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
 NOREPLICATION NOINHERIT BYPASSRLS;
ALTER ROLE health_backup_reader SET default_transaction_read_only=on;
ALTER ROLE health_backup_reader SET statement_timeout='15min';
ALTER ROLE health_backup_reader SET idle_in_transaction_session_timeout='15min';

DO $grant$
DECLARE schema_name text;
BEGIN
 FOREACH schema_name IN ARRAY ARRAY['public','auth','supabase_migrations','health_writer'] LOOP
  IF EXISTS(SELECT 1 FROM pg_namespace WHERE nspname=schema_name) THEN
   EXECUTE format('GRANT USAGE ON SCHEMA %I TO health_backup_reader',schema_name);
   EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO health_backup_reader',schema_name);
   EXECUTE format('GRANT SELECT ON ALL SEQUENCES IN SCHEMA %I TO health_backup_reader',schema_name);
  END IF;
 END LOOP;
END $grant$;
-- New tables/functions must be explicitly reviewed with the next schema change.
-- There are no automatic ownership, default DML or writer-execute grants.
CREATE SCHEMA health_backup_control AUTHORIZATION postgres;
REVOKE ALL ON SCHEMA health_backup_control FROM PUBLIC;
GRANT USAGE ON SCHEMA health_backup_control TO health_backup_reader;
CREATE FUNCTION health_backup_control.export_role_catalog() RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $fn$
BEGIN
 IF session_user<>'health_backup_reader' OR current_setting('transaction_read_only')<>'on' THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='readonly backup principal required'; END IF;
 RETURN (SELECT jsonb_agg(to_jsonb(r) ORDER BY rolname) FROM pg_catalog.pg_authid r);
END $fn$;
REVOKE ALL ON FUNCTION health_backup_control.export_role_catalog() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION health_backup_control.export_role_catalog() TO health_backup_reader;
COMMENT ON SCHEMA health_backup_control IS 'HEALTH_COMPLETE_READER_V1_NO_CLINICAL_DML';
COMMENT ON FUNCTION health_backup_control.export_role_catalog() IS
 'Fixed complete role-secret read capability; no arguments, file access, DDL or publication';
COMMIT;
