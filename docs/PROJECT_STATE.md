# Project State

Status: AUDIT REMEDIATION IN PROGRESS; FULL MIGRATION NO-GO; CUTOVER NO-GO

## Canonical boundary

- Existing Drive-native HealthDB remains the canonical source of truth until explicit cutover.
- Full migration has not begun.
- No cutover has occurred.
- Legacy HealthDB GitHub repositories are not migration inputs.

## MVP

MVP operational acceptance is PASS:
- representative migration fidelity PASS;
- owner PWA visual verification PASS;
- read-only Auth/RLS PASS;
- independent Sources backup PASS;
- independent database snapshot/readback PASS;
- isolated MVP restore PASS;
- scheduler manual bootstrap and sequential daily-chain test PASS;
- schedules enabled.

## Pre-migration hardening completed in code

- PWA runtime JavaScript is first-party only; runtime jsDelivr dependency removed.
- PWA CSP permits scripts only from self.
- GitHub Pages Actions are pinned to immutable full commit SHAs.
- Browser security validation checks exact required SELECT grants, policy shape, app_readers/auth.uid gating, technical-table isolation, default privileges, public views and SECURITY DEFINER functions.
- Auth validation requires exactly one active confirmed non-anonymous owner and matching app_reader.
- `supabase/migrations/` mirrors the live timestamped migration ledger and is canonical for schema reconstruction.
- secure default privileges are now represented in the live migration history.
- full migration has an executable private-package runner: seal -> verify -> stage -> exact fingerprints -> guarded commit -> exact public compare.
- full migration commit requires a PREPARED HEALTH operation plus the explicit authorization token `FULL_MIGRATION_AUTHORIZED`.
- old Drive-native HealthDB freeze is defined through its own PREPARED maintenance Change Log row occupying the single-writer slot; the sealed migration package records that freeze operation ID/state and zero other unfinished operations, and the old Change Log must be reread immediately before target commit.
- Auth recovery is explicit: create the replacement sole owner and rebind app_readers; medical IDs do not depend on the Auth UUID.
- recovery documentation requires real restore drills; checksum round-trip alone is not called a restore.
- scheduler code pins Ubuntu 24.04 and checksum-verifies exact rclone v1.75.1.
- new scheduler database backups include the Supabase migration-history schema/data.

## Current validation

- Live Supabase project: ACTIVE_HEALTHY, PostgreSQL 17.
- Live Auth invariants: PASS on 2026-10-08.
- Live browser/database security invariants: PASS on 2026-10-08.
- Canonical timestamped migration ledger: 9 migrations.
- Public HEALTH code validation: PASS for commit `1cf7a08bbf440cc9047cbcf40bd3b3e1048a36e0`, run `37751436255`.
- A real GitHub scheduled daily pipeline was observed: run `37743776377` SUCCESS. It produced five database dumps, copied/verified Sources, proved primary inventory unchanged, and passed database/source verification plus five-file round-trip SHA-256.
- Latest scheduled database backup used for fresh restore evidence: `2026-10-08T07-30-49Z`.
- Fresh isolated restore drill rerun (run `37690089948`, attempt 2): SUCCESS against that latest backup; roles/schema/data restore PASS, migration history 9/9 PASS, exact 15-table medical-domain fingerprint PASS, replacement-owner Auth recovery PASS, restored Auth/security PASS.
- Private Drive capture extractor is live-audited on scheduler main: run `37752859591` SUCCESS; 267 records, 1414 Labs rows, 23 Registry-linked Sources, all 15 target tables and Historical manifest processed read-only.
- Scheduler main commit for the fail-closed capture/orchestration path: `31d93b3e83279239a07b4357366710e10e711893`.

## Owner gates

1. **Supabase region** — RESOLVED: owner explicitly accepted the existing `us-west-1` project; no region migration is requested before full migration.
2. **Supabase Auth dashboard** — RESOLVED by prior owner confirmation: public self-signup/new-user creation and anonymous sign-ins were disabled; subsequent hardening did not modify Auth dashboard configuration.
3. **Public Git commit email privacy** — RESOLVED: owner accepts the existing public commit-history email exposure and does not want history rewritten.
4. **Post-hardening PWA smoke** — PASS by owner: login succeeded and multiple records/pages were checked after first-party Auth-client hardening.

## Final pre-migration audit

Current verdict: **PASS for full-migration readiness; owner authorization still required.**

2026-10-08 remediation evidence:
- the old Drive-native freeze operation ID is now treated as the exact opaque legacy Change Log value (for example `MAINT-011`), while only the new HEALTH target operation uses a UUID;
- migration package contract is schema v2 and binds `capture_mode=migration` plus `source_location_mode=new-health-primary`;
- package PRIMARY source locations are required to point to verified objects under the new `HEALTH/Sources`; old Drive IDs/URLs may remain only as private provenance;
- private scheduler extractor has a read-only `audit` mode and a separately gated authorized migration path; medical package data is ephemeral and is not published as GitHub artifacts or logs;
- preferred private `migrate` orchestration is capture -> materialize/round-trip-verify new Sources -> seal/verify -> isolated stage -> **fresh Registry + freeze reread** -> guarded target commit -> exact public comparison;
- full-migration build/migrate refuses to start without both the literal `FULL_MIGRATION_AUTHORIZED` token and the matching live legacy PREPARED freeze operation ID;
- public HEALTH hardening commit `1cf7a08bbf440cc9047cbcf40bd3b3e1048a36e0` passed CI;
- private scheduler capture/orchestration commit `31d93b3e83279239a07b4357366710e10e711893` passed live Drive capture audit on main;
- scheduled backup execution has now been observed as a real `event=schedule` SUCCESS, not merely a manual/bootstrap run;
- the newest scheduled five-file backup was restored in an isolated local Supabase with exact medical-domain, migration-history, Auth and security validation PASS;
- live production Auth/security invariants remain PASS;
- legacy GitHub HealthDB repositories are not migration inputs or runtime dependencies;
- the old Drive-native HealthDB is used only as the canonical migration source until cutover; new HEALTH record text is stored in PostgreSQL and active source PRIMARY objects belong under the new `HEALTH/Sources`.

**Audit A/B reconciliation — 2026-10-08:** auditor B found B-04: text-only recovery PASS could finalize a newer operation. B-04 code remediation is now merged in HEALTH `c423d4a4` and private SHEDULLER `27a6c20c`: operation-bound backup/source/restore evidence, authenticated successful restore run and fail-closed private finalization. Synthetic CI PASS, but a real post-full-migration recovery proof cannot exist before authorized migration. Auditor A's A-05 Source recovery/rebind tool was added, while a complete lost-PRIMARY and PWA acceptance remains mandatory before cutover.

**Full migration has not been run. Cutover has not been authorized.**

## Non-blocking advisor status

- Technical public tables intentionally have RLS with no browser policies.
- Leaked-password protection is unavailable on the current Free plan.
- Newly created covering indexes can remain reported as unused until traffic exercises them.

## Post-migration / cutover boundary

Full migration readiness is not the same as cutover readiness.

- The old Drive-native HealthDB remains canonical until explicit cutover.
- After full migration, require exact post-load validation, independent backup verification and final old-HealthDB delta = empty.
- The controlled Health API / AI write path is still deferred and is required before normal post-cutover ChatGPT write operations.
- The current external ChatGPT Project Prompt remains Drive-native until cutover. A replacement HEALTH prompt must be issued only after the new backend/write path is accepted.
- A clean new ChatGPT Project is recommended after cutover rather than carrying forward the old project's accumulated architecture context.
- Legacy `HEALTH_DB_old` retention/deletion is a separate post-cutover decision after recovery evidence is accepted.

## Full-migration gate

Historic passes are retained. B-04 code remediation is now merged with synthetic tests PASS. A fresh independent audit acceptance and the owner's separate full-migration authorization remain necessary before execution. No full migration or cutover is authorized.

Full migration may begin only after a **separate explicit owner authorization**. The private migration path requires the literal `FULL_MIGRATION_AUTHORIZED` token, a new HEALTH PREPARED target operation UUID and the matching old-HealthDB PREPARED legacy freeze operation ID.

At execution time the process must:
1. create/hold the dedicated old Drive-native PREPARED freeze;
2. capture a fresh frozen Registry/REC/Sources snapshot;
3. materialize and verify new `HEALTH/Sources` PRIMARY objects;
4. seal/verify and load isolated staging;
5. re-read the Registry and old freeze immediately before target commit and abort on any change;
6. guarded-commit the target medical domain;
7. exact-compare public tables to the sealed package;
8. rerun all impacted Validation and operation-scoped audits;
9. capture a NEW post-commit immutable backup and Source manifest, independently restore that exact dataset (15 tables, Auth/security and original Sources), and preserve actual run evidence;
10. finalize only through the private B-04 verifier: bind UUID, package fingerprint, backup/Source manifest SHA-256, successful authenticated restore run and actual recovered fingerprints. Text-only PASS is never enough.

The old Drive-native HealthDB remains canonical until a later explicit cutover authorization.

Cutover remains a separate owner decision and is not authorized by pre-migration audit PASS.
