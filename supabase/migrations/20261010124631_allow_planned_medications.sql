-- Preserve planned medication status from the canonical Drive-native source.
-- Only widens the existing CHECK; no rows, RLS policies or grants are changed.
set local lock_timeout = '10s';
alter table public.medications drop constraint medications_status_check;
alter table public.medications add constraint medications_status_check
  check (status in ('active', 'inactive', 'planned'));
