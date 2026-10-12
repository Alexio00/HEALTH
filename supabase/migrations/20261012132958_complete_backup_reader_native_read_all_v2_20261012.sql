-- Supabase owns Auth schema: postgres cannot grant all of its USAGE/SELECT ACLs.
-- Native read-all capability includes role hashes and future database tables.
-- No role SET, delegation, object ownership or data modification is granted.
BEGIN;
DO $check$
BEGIN
 IF current_database()<>'postgres' OR current_user<>'postgres' OR
    obj_description('health_backup_control'::regnamespace,'pg_namespace')<>'HEALTH_COMPLETE_READER_V1_NO_CLINICAL_DML' THEN
  RAISE EXCEPTION 'reviewed backup capability identity required'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='health_backup_reader' AND
    NOT rolsuper AND NOT rolcreaterole AND NOT rolcreatedb AND NOT rolinherit AND rolbypassrls) OR
    EXISTS(SELECT 1 FROM pg_auth_members WHERE member='health_backup_reader'::regrole) THEN
  RAISE EXCEPTION 'reader attributes or membership differ'; END IF;
END $check$;
GRANT pg_read_all_data TO health_backup_reader WITH ADMIN FALSE, INHERIT TRUE, SET FALSE;
DO $verify$
BEGIN
 IF NOT has_schema_privilege('health_backup_reader','auth','USAGE') OR
   EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname IN ('public','auth','supabase_migrations','health_writer') AND c.relkind IN ('r','p','S')
     AND NOT has_table_privilege('health_backup_reader',c.oid,'SELECT')) OR
   EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND c.relkind IN ('r','p')
     AND (has_table_privilege('health_backup_reader',c.oid,'INSERT') OR has_table_privilege('health_backup_reader',c.oid,'UPDATE')
       OR has_table_privilege('health_backup_reader',c.oid,'DELETE') OR has_table_privilege('health_backup_reader',c.oid,'TRUNCATE'))) OR
   EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND has_schema_privilege('health_backup_reader',n.oid,'USAGE')
     AND p.prosecdef AND has_function_privilege('health_backup_reader',p.oid,'EXECUTE')
     AND NOT(n.nspname='health_backup_control' AND p.proname='export_role_catalog' AND p.pronargs=0)) THEN
  RAISE EXCEPTION 'native read-all capability postflight failed'; END IF;
END $verify$;
COMMENT ON ROLE health_backup_reader IS 'HEALTH_COMPLETE_READER_V2_NATIVE_READ_ALL_NO_DML';
COMMIT;
