-- Draft schema supplement: not for direct production execution.
alter table public.vaccination_evidence add column antigen_key text;
alter table public.vaccination_evidence
 add constraint evidence_antigen_reference
 foreign key (administration_id, antigen_key)
 references public.vaccination_administration_antigens(administration_id, antigen_key);

alter table public.vaccination_plan_links add column antigen_key text not null;
alter table public.vaccination_plan_links
 add constraint plan_antigen_reference
 foreign key (administration_id, antigen_key)
 references public.vaccination_administration_antigens(administration_id, antigen_key);

-- Also update both evidence uniqueness and plan primary key to include
-- antigen_key before producing the reviewed v2 migration.
