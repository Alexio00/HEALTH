-- HEALTH single-user Auth invariants.
-- Does not validate dashboard-only settings such as "Allow new users to sign up".

do $$
declare
  v_auth_count integer;
  v_reader_count integer;
  v_mismatch_count integer;
begin
  select count(*) into v_auth_count
  from auth.users
  where deleted_at is null;

  if v_auth_count <> 1 then
    raise exception 'AUTH: expected exactly one active auth user, found %', v_auth_count;
  end if;

  select count(*) into v_reader_count
  from public.app_readers;

  if v_reader_count <> 1 then
    raise exception 'AUTH: expected exactly one app_reader, found %', v_reader_count;
  end if;

  select count(*) into v_mismatch_count
  from public.app_readers r
  left join auth.users u on u.id = r.user_id and u.deleted_at is null
  where u.id is null;

  if v_mismatch_count <> 0 then
    raise exception 'AUTH: app_reader does not match the sole active auth user';
  end if;
end
$$;
