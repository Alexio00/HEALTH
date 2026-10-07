begin;

alter table public.id_reservations
  add column metadata jsonb not null default '{}'::jsonb;

commit;
