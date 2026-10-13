# Vaccination registry v1 — technical handoff (design branch)

Status: **schema proposal, NOT DEPLOYED**. Conceptual entities confirmed by owner on
2026-10-13. Related backlog issues #41 (schema) and #42 (historical reconciliation).
The shared deadlines registry #40 is out of scope and owned in another chat.

## Scope

The SQL proposal is `docs/proposals/vaccination_registry_v1.sql`.
It introduces six normalized tables; no patient facts or records. Schema names
and privilege boundaries are proposed for independent Writer/security review.
Do not merge it into `main`, run it on canonical Supabase, or infer clinical
write authorization from owner approval of this *structure*.

- `vaccination_courses`: optional course/season identity. Course identifiers
  never substitute for proven medical chronology.
- `vaccination_antigens`: a normalized catalog of independently supported
  vaccination targets.
- `vaccination_administrations`: ONE administered product per event; the
  event may cover multiple targets. Unknown source values stay NULL, no invented
  dose/course. States: pending, verified, retracted.
- `vaccination_administration_antigens`: many-to-many event/antigen.
- `vaccination_evidence`: exact REC and optional Source references with
  independent roles administered, prescribed or supporting. A basis REC by
  itself must not be labeled a physician's prescription.
- `vaccination_plan_links`: a proven explicit relation between a plan item
  and an administration; no linking by date alone.

Stage **display** is `V1, V2, ...` and `Rv` (capital R, lowercase v).
Canonical model uses `stage_kind` and optional `dose_number`; the literal
source stage, including any R1 or V1, remains in `stage_source_text`.
Do not add batch numbers, manufacturer or injection site; owner excluded these.

## Required coordination with parallel Writer development

1. Reader schema shape and RLS/GRANT proposal must undergo a separate review.
   In `public`, RLS is enabled and `authenticated` can only SELECT for
   registered `app_readers`. Browser insert/update/delete is forbidden.
2. **No Writer SQL publication is implemented here.** Coordinate a bounded,
   separately reviewed addition to the Writer's allowlisted delta schema, exact
   owner approval and candidate SHA, before-state hashes, independent
   clinical/source verifier and one-operation transactional publication.
3. Validation must enforce at least:
   - verified event has real administration evidence, date and antigen;
   - all role-specific REC/source links resolve;
   - all `source_id` on an event's evidence also belongs to that REC's
     documented provenance unless the owner explicitly approves a new
     evidence relation;
   - retracting/altering an administration adjusts dependent derived state;
   - plan `fulfilled` links are independently verified, not inferred;
   - multiple vaccines in one visit remain separate, combination targets do
     not clone an injection, seasonal courses remain distinct;
   - no conflicting verified dose identities; ambiguous events stay pending.
4. Schema migration, Writer delta, and Validation modifications must be
   synchronized with the parallel Writer PR #35 and any later head changes.
   Do not rebase/squash or merge another chat's Writer branch.
5. Reconcile the current Supabase canonical schema against this proposal,
   generate an actual migration via the project's CLI and test it against
   a **synthetic disposable PostgreSQL 17 database**. Production rollout
   requires independent security review, a new exact `main` SHA acceptance,
   and separately approved bounded publication of medical rows.
6. PWA adaptations belong in a separate `pwa` PR only after a verified
   read contract is available; keep the existing page operating meanwhile.

## Testing / acceptance

Tests should cover NULL provenance, duplicate REC evidence, withdrawn
records, independently administered products at one appointment,
combination targets, seasonal recurrence, doses R1 vs V1, pending
course membership, absent plan dates, and denied unauthorized SQL writes.
Run role-level SELECT/INSERT/UPDATE/DELETE negatives for `anon`,
`authenticated` and `service_role`, and authorized reader SELECT.

No patient data, source bytes, real vaccine history or credentials in GitHub,
test fixtures, logs or actions artifacts. Historical reconciliation #42 must
remain in the private medical context, not written to public Issues.

## Release boundary

This proposal contains **no SQL runtime change**, no migration in
`supabase/migrations`, no Writer code change, and no authorization/Edge
configuration change. Merging into `main` would still change the
Writer-accepted commit SHA; keep draft and coordinate release separately.
