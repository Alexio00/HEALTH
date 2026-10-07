# Project State

Status: MVP technical acceptance PASS; scheduler bootstrap pending

## Confirmed

- Public repository `Alexio00/HEALTH` is intentionally safe for public inspection.
- Private scheduler repository `Alexio000/SHEDULLER` is connected and contains manual bootstrap workflows for database backup, Sources backup, verification and keepalive.
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

Committed to the private scheduler repository as manual-only workflows:
- HEALTH database backup;
- HEALTH Sources backup;
- HEALTH backup verification;
- HEALTH keepalive.

Schedules are intentionally not enabled until required repository secrets are configured and each workflow passes once manually.

## Remaining owner-side setup

- Configure private scheduler secrets required for Supabase database access and the two Google Drive remotes.

## Advisor status

- Security: intentional INFO notices for browser-hidden technical tables remain. The leaked-password-protection advisor warning is a current Free-plan limitation; Supabase documents this feature as Pro-and-above.
- Performance: no unindexed foreign keys remain. Newly created indexes may appear as unused until production-sized traffic exists.

## Next gate

After scheduler secrets are configured, run all four workflows manually once. If they PASS, enable schedules and complete final operational acceptance.

Full migration remains blocked until the owner explicitly authorizes it after this gate.

When authorized, migration starts from a fresh Drive-native snapshot and isolated staging validation; the representative MVP is replaced rather than treated as an incremental baseline. Cutover remains a separate owner decision.
