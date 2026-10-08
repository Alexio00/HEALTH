-- Synthetic disposable PostgreSQL only. Never run against HEALTH production.
\set ON_ERROR_STOP on
create role service_role nologin bypassrls;
create table public.operations (id integer);
create table public.system_state (id integer);
create table public.validation_results (id integer);
create table public.validation_checks (id integer);
create table public.id_reservations (id integer);
grant all privileges on
  public.operations, public.system_state, public.validation_results,
  public.validation_checks, public.id_reservations
to service_role;

do $$
declare tbl text;
begin
  foreach tbl in array array['operations','system_state','validation_results',
                             'validation_checks','id_reservations']
  loop
    if not has_table_privilege('service_role','public.'||tbl,'UPDATE') then
      raise exception 'invalid synthetic setup: role cannot initially UPDATE %',tbl;
    end if;
  end loop;
end $$;

\ir ../../supabase/migrations/20261009000000_restrict_service_role_migration_controls.sql

do $$
declare tbl text;
declare action text;
begin
  foreach tbl in array array['operations','system_state','validation_results',
                             'validation_checks','id_reservations']
  loop
    if not has_table_privilege('service_role','public.'||tbl,'SELECT') then
      raise exception 'technical readback removed on %',tbl;
    end if;
    foreach action in array array['INSERT','UPDATE','DELETE','TRUNCATE',
                                  'TRIGGER','REFERENCES']
    loop
      if has_table_privilege('service_role','public.'||tbl,action) then
        raise exception 'privileged role bypass still allowed: %.%',tbl,action;
      end if;
    end loop;
  end loop;
end $$;

-- Re-running the convergence must not restore DML.
\ir ../../supabase/migrations/20261009000000_restrict_service_role_migration_controls.sql

do $$
begin
  if has_table_privilege('service_role','public.operations','UPDATE')
     or has_table_privilege('service_role','public.system_state','UPDATE') then
    raise exception 'idempotent re-application restored privileged UPDATE';
  end if;
end $$;
