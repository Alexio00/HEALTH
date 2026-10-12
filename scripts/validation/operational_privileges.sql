-- Read-only catalog audit. This does not inspect Actions secret values or revoke roles.
BEGIN READ ONLY;
SELECT r.rolname,r.rolcanlogin,r.rolsuper,r.rolcreaterole,r.rolcreatedb,r.rolbypassrls,
 coalesce((SELECT jsonb_agg(jsonb_build_object('role',g.rolname,'admin',m.admin_option,'inherit',m.inherit_option,'set',m.set_option)) FROM pg_auth_members m JOIN pg_roles g ON g.oid=m.roleid WHERE m.member=r.oid),'[]') AS inherited_roles
FROM pg_roles r WHERE r.rolname IN ('health_backup_reader','service_role','health_test_ci','health_test_writer_role') ORDER BY r.rolname;
SELECT r.rolname,t.table_name,
 has_table_privilege(r.oid,format('public.%I',t.table_name),'SELECT') can_select,
 has_table_privilege(r.oid,format('public.%I',t.table_name),'INSERT') can_insert,
 has_table_privilege(r.oid,format('public.%I',t.table_name),'UPDATE') can_update,
 has_table_privilege(r.oid,format('public.%I',t.table_name),'DELETE') can_delete,
 has_table_privilege(r.oid,format('public.%I',t.table_name),'TRUNCATE') can_truncate
FROM pg_roles r CROSS JOIN (VALUES ('records'),('labs'),('sources'),('source_locations'),('operations'),('app_readers')) t(table_name)
WHERE r.rolname IN ('health_backup_reader','service_role','anon','authenticated') AND to_regclass(format('public.%I',t.table_name)) IS NOT NULL ORDER BY 1,2;
SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) arguments,
 p.prosecdef,pg_get_userbyid(p.proowner) owner,
 has_function_privilege('service_role',p.oid,'EXECUTE') service_role_execute
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public' AND p.prosecdef ORDER BY 1,2,3;
SELECT ssl,version,cipher FROM pg_stat_ssl WHERE pid=pg_backend_pid();
-- SSL above belongs to THIS audit connection, not the owner-held local executor.
COMMIT;
