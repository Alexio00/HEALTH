-- B04-M03: service_role is for application API access, not migration control.
-- The private full-migration executor uses a separately controlled direct
-- PostgreSQL connection. Do not expose that connection to browser clients.
-- Keep SELECT for technical readback; remove every mutation capability.
-- Idempotent: the file can be re-applied safely to an existing deployment.

revoke all privileges on table
  public.operations,
  public.system_state,
  public.validation_results,
  public.validation_checks,
  public.id_reservations
from service_role;

grant select on table
  public.operations,
  public.system_state,
  public.validation_results,
  public.validation_checks,
  public.id_reservations
 to service_role;
