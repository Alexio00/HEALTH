begin;
revoke all on public.operations, public.id_reservations, public.validation_checks,
  public.validation_results, public.system_state from anon, authenticated, public;
commit;
