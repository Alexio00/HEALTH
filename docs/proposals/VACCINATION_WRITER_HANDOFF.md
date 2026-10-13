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

Stage **display** is `V1, V2, ...`, `Rv`, `Rv1`, `Rv2`, ...
(capital Latin R, lowercase Latin v). In the current provisional SQL shape,
`stage_kind='dose'` with `dose_number=1` produces `V1`;
`stage_kind='revaccination'` with `dose_number=NULL` produces `Rv`;
`stage_kind='revaccination'` with `dose_number=1` or `2` produces
`Rv1` or `Rv2`. `stage_kind='unknown'` may not have a numbered stage.
The literal source stage, including R1, V1 or RV, remains in
`stage_source_text`; the owner-approved clinical stage is independent.
The previous check constraint incorrectly rejected numbered revaccinations;
it was corrected in this non-deployed proposal.
Do not add batch numbers, manufacturer or injection site; owner excluded these.

## Multivalent product and antigen-specific stage — PROPOSAL FOR OWNER DECISION

**Approved by the owner on 2026-10-13; deployment awaits Writer integration.** The owner raised a concern that one
combined administration may have different vaccine-course stages for its
several target infections. The provisional six-table SQL proposal currently
stores one stage at the administration level. That cannot safely convey an
antigen-specific booster stage without inventing the same stage for every
target of a combination product.

Approved target contract:

1. Keep `vaccination_administrations` as one real physical administration
   with one product, date and its event-level original source evidence.
2. Use `vaccination_administration_antigens` for each distinct infection
   protected against by that event. Store **per-antigen** clinical stage
   (`Vn`, `Rv`, `Rvn`, or unknown), separately verified provenance, and
   if justified a per-antigen course identity. Moving stage kind/number and
   course association from event to relation avoids competing sources of
   truth; keep an original event-level source stage literal for history.
3. Treat `vaccination_plan_links` and its independent proof so a plan for
   one infection is fulfilled only by the matching antigen relationship,
   not by the mere presence of the combined injection.
4. Preserve explicit null for antigen-specific unknown stage. Never copy a
   documented stage for target A to targets B/C of the same product.

Approved PWA projection:

- **History:** one parent row for each real administration, with infection
  chips/tags and an expandable detail area listing each antigen and its
  **own** stage. Count as one administration, never three doses.
- **Latest by infection:** one row for each infection, with a link to its
  shared administration, stage for that infection and optionally a visual
  combined-product indicator. The same administration may be referenced
  from multiple infection rows without incrementing administered-dose count.
- **Planned:** one obligation per proven planned infection/dose; aggregate
  several linked targets visually only when the plan actually supports it.

This direction is owner-approved; draft SQL patches are not an executable production migration. Do not prematurely
conflate a dose number with a single product's global stage. Run synthetic
cross-antigen cases through Writer/verifier/reader contract before rollout.

### Stage-shape acceptance matrix for the current interim proposal

| stage_kind | dose_number | display | allowed |
| --- | ---: | --- | --- |
| dose | 1 | V1 | yes |
| dose | 2 | V2 | yes |
| revaccination | NULL | Rv | yes |
| revaccination | 1 | Rv1 | yes |
| revaccination | 2 | Rv2 | yes |
| revaccination | 999 | Rv999 | yes, bound |
| unknown | NULL | unknown | yes |
| unknown | 1 | invalid | no |
| dose | 0 | invalid | no |
| revaccination | -1 | invalid | no |

This acceptance matrix still needs actual disposable PostgreSQL 17 testing
when a reviewed migration is prepared. It is not a CI PASS or a production
migration. Unknown stages must not be silently inferred from chronology.


## V2 implementation queue (approved, not released)

Draft SQL sequence for disposable tests: v1, then
`vaccination_v2_antigen_stage_patch.sql`,
`vaccination_v2_antigen_relations_draft.sql`, and
`vaccination_v2_antigen_keys_draft.sql`.
Do not ship sequentially: replace with ONE reviewed schema migration.
Frontend PR #59 (stacked on PR #51) adds multivalent infection tags,
per-antigen latest rows and synthetic projection/tests. The canonical
reader query, final Writer delta and full verification are still pending.

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

## Private pending-change handoff (owner-only Drive)

An additional owner-approved **private clinical correction batch** is awaiting
Writer capability and independent validation. The authoritative candidate
is an **owner-only Google Drive document**:

[Private pending correction package — restricted access](https://docs.google.com/document/d/153X5Bc6pa9xWnQNmlOgymQJ7Q6Ns8jOJHFP7adquxEE/edit)

The link is a coordination pointer only; it is not clinical data authorization.
Do not copy its contents, patient identifiers, REC facts, dates or source bytes
into this public repository, PR comments, tests or CI logs.
The parallel Writer development must finish and its current SHA must be
accepted before the clinical candidate can be constructed or published.
Use only the bounded Writer and independent clinical verifier; never SQL
admin direct writes. This draft is not a production migration.

## Release boundary

This proposal contains **no SQL runtime change**, no migration in
`supabase/migrations`, no Writer code change, and no authorization/Edge
configuration change. Merging into `main` would still change the
Writer-accepted commit SHA; keep draft and coordinate release separately.
