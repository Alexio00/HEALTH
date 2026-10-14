-- Completes draft vaccination v2 keys after both earlier SQL proposal patches.
-- All tables are empty pre-deployment. No canonical database writes.
drop index public.vaccination_evidence_unique_idx;
create unique index vaccination_evidence_unique_idx
 on public.vaccination_evidence
 (administration_id, antigen_key, record_id, evidence_role, source_id)
 nulls not distinct;

alter table public.vaccination_plan_links
 drop constraint vaccination_plan_links_pkey;
alter table public.vaccination_plan_links
 add constraint vaccination_plan_links_pkey
 primary key(administration_id, antigen_key, plan_item_id);

-- Final production change MUST be one reviewed, tested migration, with
-- Writer allowlist, verification, RLS and negative permission tests.
