-- DRAFT ONLY. Apply after vaccination_registry_v1.sql in disposable PG17.
-- Effective design is v1 plus this antigen-specific patch; not a migration.
-- Never run on canonical Supabase before Writer/security acceptance.
alter table public.vaccination_administrations
 drop constraint vaccination_administrations_stage_shape,
 drop column course_id,
 drop column stage_kind,
 drop column dose_number;
drop index public.vaccination_administrations_course_idx;

alter table public.vaccination_administration_antigens
 add column course_id uuid references public.vaccination_courses(course_id),
 add column stage_kind text not null default 'unknown'
   check(stage_kind in ('dose','revaccination','unknown')),
 add column dose_number integer check(dose_number between 1 and 999),
 add column stage_source_text text,
 add column stage_verification_note text,
 add constraint vaccination_antigen_stage_shape
   check(stage_kind <> 'unknown' or dose_number is null);
create index vaccination_antigens_course_idx
 on public.vaccination_administration_antigens(course_id);

-- One real injection with one or several infection-specific stage rows.
-- V1 = dose/1; Rv = revaccination/NULL; Rv2 = revaccination/2.
-- Unknown stages are not assigned from another infection's stage.
