-- HEALTH browser/database security invariants.
-- Run after schema/security migrations. Any violation raises an exception.

do $$
declare
  bad text;
begin
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

  -- 2. anon must have no table privileges in public.
  select string_agg(format('%I:%s', table_name, privilege_type), ', ')
    into bad
  from information_schema.role_table_grants
  where table_schema = 'public'
    and grantee = 'anon';

  if bad is not null then
    raise exception 'SECURITY: anon has public table privileges: %', bad;
  end if;

  -- 3. authenticated may only SELECT from the explicit browser allow-list.
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

  -- 4. postgres defaults for future public tables/sequences/functions
  -- must not grant anon/authenticated automatically.
  select string_agg(format('%s/%s=%s', coalesce(n.nspname,'GLOBAL'), d.defaclobjtype, d.defaclacl::text), '; ')
    into bad
  from pg_default_acl d
  left join pg_namespace n on n.oid = d.defaclnamespace
  where d.defaclrole = (select oid from pg_roles where rolname = 'postgres')
    and (
      (n.nspname = 'public' and d.defaclobjtype in ('r','S','f')
        and (
          d.defaclacl::text like '%anon=%'
          or d.defaclacl::text like '%authenticated=%'
        )
      )
      or
      (n.nspname is null and d.defaclobjtype = 'f'
        and d.defaclacl::text like '%=X/%'
      )
    );

  if bad is not null then
    raise exception 'SECURITY: unsafe postgres default privileges: %', bad;
  end if;
end
$$;
