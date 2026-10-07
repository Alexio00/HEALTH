-- HEALTH browser/database security invariants.
-- Run after every schema/security change. Any violation raises an exception.

do $$
declare
  bad text;
  missing text;
begin
  -- Make pg_policies / pg_get_expr rendering deterministic. Without this,
  -- supabase_admin's default search_path includes auth and the exact same
  -- auth.uid() policy can deparse as uid(), causing a false security failure.
  perform set_config('search_path', 'pg_catalog,public', true);

  -- 1. Every public table must have RLS enabled.
  select string_agg(format('%I.%I', n.nspname, c.relname), ', ')
    into bad
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relkind in ('r','p')
    and not c.relrowsecurity;

  if bad is not null then
    raise exception 'SECURITY: public tables without RLS: %', bad;
  end if;

  -- 2. anon must have no public table privileges.
  select string_agg(format('%I:%s', table_name, privilege_type), ', ')
    into bad
  from information_schema.role_table_grants
  where table_schema = 'public'
    and grantee = 'anon';

  if bad is not null then
    raise exception 'SECURITY: anon has public table privileges: %', bad;
  end if;

  -- 3. authenticated must have SELECT on every browser allow-list table.
  with allowed(table_name) as (
    values
      ('app_readers'),('domains'),('records'),('record_domains'),('sources'),
      ('source_locations'),('record_sources'),('cases'),('case_links'),('analytes'),
      ('labs'),('medications'),('monitoring'),('plan_items'),('questions')
  )
  select string_agg(a.table_name, ', ')
    into missing
  from allowed a
  where not has_table_privilege('authenticated', format('public.%I', a.table_name), 'SELECT');

  if missing is not null then
    raise exception 'SECURITY: authenticated missing required SELECT grants: %', missing;
  end if;

  -- 4. authenticated must have no public privileges except SELECT on the allow-list.
  select string_agg(format('%I:%s', table_name, privilege_type), ', ')
    into bad
  from information_schema.role_table_grants
  where table_schema = 'public'
    and grantee = 'authenticated'
    and (
      privilege_type <> 'SELECT'
      or table_name not in (
        'app_readers','domains','records','record_domains','sources',
        'source_locations','record_sources','cases','case_links','analytes',
        'labs','medications','monitoring','plan_items','questions'
      )
    );

  if bad is not null then
    raise exception 'SECURITY: authenticated has unexpected public privileges: %', bad;
  end if;

  -- 5. Browser tables must expose exactly one SELECT policy to authenticated,
  -- and no write/ALL policies.
  with allowed(table_name) as (
    values
      ('app_readers'),('domains'),('records'),('record_domains'),('sources'),
      ('source_locations'),('record_sources'),('cases'),('case_links'),('analytes'),
      ('labs'),('medications'),('monitoring'),('plan_items'),('questions')
  ),
  policy_shape as (
    select a.table_name,
           count(*) filter (
             where p.cmd = 'SELECT'
               and 'authenticated' = any(p.roles)
               and not ('anon' = any(p.roles))
           ) as reader_select_count,
           count(*) filter (where p.cmd in ('INSERT','UPDATE','DELETE','ALL')) as write_count
    from allowed a
    left join pg_policies p
      on p.schemaname = 'public' and p.tablename = a.table_name
    group by a.table_name
  )
  select string_agg(
           format('%I(select=%s,write=%s)', table_name, reader_select_count, write_count),
           ', '
         )
    into bad
  from policy_shape
  where reader_select_count <> 1 or write_count <> 0;

  if bad is not null then
    raise exception 'SECURITY: browser policy shape mismatch: %', bad;
  end if;

  -- 6. app_readers must be self-only via auth.uid().
  select string_agg(policyname, ', ')
    into bad
  from pg_policies
  where schemaname = 'public'
    and tablename = 'app_readers'
    and cmd = 'SELECT'
    and (
      qual is null
      or position('auth.uid' in lower(qual)) = 0
      or position('user_id' in lower(qual)) = 0
    );

  if bad is not null then
    raise exception 'SECURITY: app_readers SELECT policy is not self-only: %', bad;
  end if;

  -- 7. Every medical browser table policy must gate through app_readers + auth.uid().
  select string_agg(format('%I:%I', tablename, policyname), ', ')
    into bad
  from pg_policies
  where schemaname = 'public'
    and tablename in (
      'domains','records','record_domains','sources','source_locations','record_sources',
      'cases','case_links','analytes','labs','medications','monitoring','plan_items','questions'
    )
    and cmd = 'SELECT'
    and (
      qual is null
      or position('app_readers' in lower(qual)) = 0
      or position('auth.uid' in lower(qual)) = 0
    );

  if bad is not null then
    raise exception 'SECURITY: medical SELECT policy missing reader/auth gate: %', bad;
  end if;

  -- 8. Technical tables must remain policy-free and browser-inaccessible.
  select string_agg(format('%I:%I', tablename, policyname), ', ')
    into bad
  from pg_policies
  where schemaname = 'public'
    and tablename in ('operations','id_reservations','validation_checks','validation_results','system_state');

  if bad is not null then
    raise exception 'SECURITY: technical table unexpectedly has browser policy: %', bad;
  end if;

  -- 9. No public views/materialized views are allowed without an explicit security review.
  select string_agg(c.relname, ', ')
    into bad
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relkind in ('v','m');

  if bad is not null then
    raise exception 'SECURITY: public views require explicit security review: %', bad;
  end if;

  -- 10. No SECURITY DEFINER functions may live in public.
  select string_agg(p.proname, ', ')
    into bad
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.prosecdef;

  if bad is not null then
    raise exception 'SECURITY: SECURITY DEFINER function in public: %', bad;
  end if;

  -- 11. Browser roles must have no public sequence privileges.
  select string_agg(format('%I:%s:%s', object_name, grantee, privilege_type), ', ')
    into bad
  from information_schema.usage_privileges
  where object_schema = 'public'
    and object_type = 'SEQUENCE'
    and grantee in ('anon','authenticated');

  if bad is not null then
    raise exception 'SECURITY: browser sequence privilege exists: %', bad;
  end if;

  -- 12. Future postgres-owned public objects must not auto-grant
  -- privileges to anon/authenticated, and PUBLIC must not receive
  -- global EXECUTE on newly created functions.
  select string_agg(
           format('%s/%s grantee=%s privilege=%s',
             coalesce(n.nspname,'GLOBAL'),
             d.defaclobjtype,
             coalesce(r.rolname,'PUBLIC'),
             x.privilege_type
           ),
           '; '
         )
    into bad
  from pg_default_acl d
  left join pg_namespace n on n.oid = d.defaclnamespace
  cross join lateral aclexplode(d.defaclacl) x
  left join pg_roles r on r.oid = x.grantee
  where d.defaclrole = (select oid from pg_roles where rolname = 'postgres')
    and (
      (
        n.nspname = 'public'
        and d.defaclobjtype in ('r','S','f')
        and r.rolname in ('anon','authenticated')
      )
      or
      (
        n.nspname is null
        and d.defaclobjtype = 'f'
        and x.grantee = 0
        and x.privilege_type = 'EXECUTE'
      )
    );

  if bad is not null then
    raise exception 'SECURITY: unsafe postgres default privileges: %', bad;
  end if;
end
$$;
