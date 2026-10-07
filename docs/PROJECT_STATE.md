# Project State

Status: MVP operational acceptance PASS; full migration awaiting owner authorization

## Confirmed

- Public repository `Alexio00/HEALTH` is intentionally safe for public inspection.
- Private scheduler repository `Alexio000/SHEDULLER` is connected and contains database backup, Sources backup, verification and keepalive workflows.
- Existing Drive-native HealthDB remains the canonical source of truth until explicit cutover.
- Supabase project `HEALTH` is connected and healthy.
- Core schema, RLS, browser grants and secure default privileges are active.
- Exactly one approved Auth reader is configured.
- Read-only PWA is deployed through GitHub Pages and owner authentication is confirmed.
- Owner visually verified imported data, Sources and navigation in the live PWA.
- Representative migration subset is imported and source-to-target fidelity checks PASS.
- Required MVP Source material is copied to primary HEALTH/Sources.
- Independent Source backup exists on the second Drive account; size and independently recomputed SHA-256 match.
- Independent logical database snapshot exists on the second Drive account and reads back exactly.
- Restore test from the independent backup snapshot restored all included tables into an isolated PostgreSQL schema with exact per-table content matches; the test schema was deleted afterward.
- MVP backup manifest exists on the independent backup Drive.
- Covering indexes were added for all foreign keys previously reported as unindexed; the performance advisor now reports no unindexed-foreign-key findings.
- No source-system medical data was deleted or moved.
- No cutover has occurred.
- Full migration has not begun.
- Public-safe full migration procedure is documented in `docs/FULL_MIGRATION_PLAN.md`.
- Lossless Drive-to-HEALTH transformation rules are documented in `docs/MIGRATION_FIELD_MAP.md`.
- Full migration will use a fresh live Google Drive snapshot; legacy HealthDB GitHub repositories are excluded as migration inputs.
- The HEALTH ID reservation ledger now has private JSON metadata capacity for preserving legacy ledger provenance without coercing old text operation IDs into new UUIDs.

## Scheduler bootstrap

Operational bootstrap is PASS.

Independently verified:
- database backup manual run PASS;
- Sources backup manual run PASS;
- backup verification manual run PASS;
- keepalive manual run PASS;
- sequential daily pipeline manual dispatch PASS in database → Sources → verification order;
- repository secrets are functionally present because all secret-dependent jobs completed successfully;
- GitHub artifacts are not used for backup payloads or inventories;
- primary Sources remained unchanged across backup inventory checks;
- independent backup Drive contains the expected database dump set and Sources copy;
- downloaded database backup round-trip SHA-256 verification PASS;
- daily backup and keepalive schedules are enabled.

The first automatic cron event has not yet occurred. This is recorded as an observation, not an acceptance blocker, because the scheduled workflow definitions are active and the same daily chain has already passed by manual dispatch.

## Remaining owner-side setup

None for MVP operational acceptance.

## Advisor status

- Security: intentional INFO notices for browser-hidden technical tables remain. The leaked-password-protection advisor warning is a current Free-plan limitation; Supabase documents this feature as Pro-and-above.
- Performance: no unindexed foreign keys remain. Newly created indexes may appear as unused until production-sized traffic exists.

## Next gate

MVP operational acceptance is complete.

Full migration is now blocked only on explicit owner authorization. No migration starts implicitly from this status update.

When authorized, migration starts from a fresh live Drive-native snapshot and isolated staging validation; the representative MVP is replaced rather than treated as an incremental baseline. Cutover remains a separate owner decision.
