# Approved vaccination v2 contract
Owner approved the design on 2026-10-13. One injection = one administration; multiple target infections = separate antigen relations. Each relation owns its own dose/revaccination stage and, when proven, course identity. Rv, Rv1 and Rv2 are supported. Unknown targets remain unknown. Do not copy stages between antigens.
The existing v1 proposal must not be deployed without the reviewed v2 follow-up. Plan fulfillment must identify a specific antigen, not merely the shared administration. Evidence may be event-wide or explicitly antigen-specific. Original source labels remain immutable.
Frontend: history groups one injection with infection chips and expandable stage details; latest has one row per infection, both linking to the same injection; plans show separately supported obligations. Pending migration/Writer review and synthetic regressions. No medical facts, source bytes, runtime SQL or patient information in this repository.

## Release blockers

The current v1 SQL is not the final schema. The approved draft stage patch moves course_id, stage_kind and dose_number from the physical administration onto each antigen relation. Before executing ANY migration, complete these missing v2 requirements:

1. Evidence can target a specific antigen or the whole injection, using nullable antigen_key and a composite foreign key.
2. Plan links require antigen_key with a composite foreign key and primary key; completion of an unrelated antigen must not close a plan.
3. Generate one reviewed migration (not separate draft ALTER files); Writer, verifier, validation, RLS, and PWA reader must be compatible.
4. The stacked frontend draft PR #59 contains a projection helper and synthetic tests, but is NOT yet wired into the live page. Do not merge until data joins and expandable tags have been integrated and tested.
