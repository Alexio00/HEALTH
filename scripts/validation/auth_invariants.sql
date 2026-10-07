-- HEALTH single-user Auth invariants.
-- Does not validate dashboard-only settings such as "Allow new users to sign up".

do $$
declare
  v_auth_count integer;
  v_reader_count integer;
  v_mismatch_count integer;
  v_unconfirmed_count integer;
  v_anonymous_count integer;
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

  select count(*) into v_unconfirmed_count
  from auth.users
  where deleted_at is null
    and email_confirmed_at is null;

  if v_unconfirmed_count <> 0 then
    raise exception 'AUTH: sole active user email is not confirmed';
  end if;

  select count(*) into v_anonymous_count
  from auth.users
  where deleted_at is null
    and coalesce(is_anonymous, false);

  if v_anonymous_count <> 0 then
    raise exception 'AUTH: anonymous Auth user is not allowed for HEALTH';
  end if;
end
$$;
