-- Register the sole active Supabase Auth user as the HEALTH browser reader.
-- Fail closed if the project does not contain exactly one active Auth user.

do $$
declare
  v_user_id uuid;
  v_count integer;
begin
  select count(*)
    into v_count
  from auth.users
  where deleted_at is null;

  if v_count <> 1 then
    raise exception 'AUTH: expected exactly one active auth user, found %', v_count;
  end if;

  select id
    into v_user_id
  from auth.users
  where deleted_at is null
  limit 1;

  insert into public.app_readers (user_id, label)
  values (v_user_id, 'owner')
  on conflict (user_id) do update
    set label = excluded.label;

  delete from public.app_readers
  where user_id <> v_user_id;
end
$$;
