# Project State

Status: B-04 INDEPENDENT B TECHNICAL GO; FINAL A READ-ONLY CHECK PENDING; FULL MIGRATION EXECUTION NO-GO; CUTOVER NO-GO

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

The independent 2026-10-08 follow-up audits disagreed: audit A gave technical GO (immediate execution NO-GO), while adversarial audit B found **3 Major** in the B-04 finalization/recovery chain and returned technical NO-GO. We apply the conservative B verdict. Three code remedies are now merged and synthetically tested; **current technical execution verdict remains NO-GO until a fresh independent re-audit accepts their new exact SHAs**, and a separate owner authorization is still required for any freeze/full migration.

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

**Audit A/B reconciliation — 2026-10-08:** auditor B found B-04: text-only recovery PASS could finalize a newer operation. First B-04 remediation was merged in HEALTH `c423d4a4` and private SHEDULLER `27a6c20c`. A subsequent focused review found a further proof-authenticity gap: an arbitrary privately stored restore proof was not demonstrably produced by the claimed successful GitHub Actions run. Private SHEDULLER [PR #10](https://github.com/Alexio000/SHEDULLER/pull/10), merged as `c8399ae8`, now requires the exact matching GitHub-produced digest-only Actions artifact as well as authenticated successful-run metadata. A real synthetic GitHub Actions artifact transport test (run `37818168954`) PASS included upload → authenticated REST/ZIP readback → SHA/run/attempt/SHA binding and negative tampering cases. It also discovered and corrected signed-download redirect handling so the Actions bearer token is not forwarded across host origins. Scheduler main recovery code CI run `37818353973` PASS. This is **synthetic integration**, NOT full-dataset disaster recovery. Auditor A's A-05 replacement-PRIMARY restore/rebind code exists; complete lost-PRIMARY and PWA original-opening exercises remain mandatory before cutover.

**Independent audit B, three Major corrections (2026-10-08):**

- B04-B-01: private scheduler [PR #11](https://github.com/Alexio000/SHEDULLER/pull/11), merged as `380c964d205b33242f5a458b03dab10f141b7f97`, scopes backup `PGOPTIONS=-c default_transaction_read_only=on` strictly to the backup read subprocess rather than mutating the parent finalizer's environment.
- B04-B-02: public HEALTH [PR #14](https://github.com/Alexio00/HEALTH/pull/14), merged as `d1bad17c93f1d28daf41f89be970f68f55e44f1c`, recalculates complete SHA-256 fingerprints of all 15 medical tables under SHARE DML-blocking locks **in the same PostgreSQL transaction** as `VALIDATED → FINALIZED`, with operation + authorization/snapshot/evidence row locking. Isolated PostgreSQL 17 synthetic tests include a real concurrent two-session writer and reject changed data (CI `37821851207`).
- B04-B-03: private scheduler PR #11 binds the *entire* `Historical` inventory to the sealed old-Drive fingerprint and byte-reads **all retained originals, including unlinked files**, from independent backup at both backup verification and isolated restore. Full-Historical corruption/omission negative tests PASS (CI `37822115414`). Public recovery contract requires the old sealed inventory digest and count.

**Important scope:** the SHA values above identify the newly merged code, not evidence that a complete production migration was run. Actual post-full-migration operation-bound backup/restore and original Sources acceptance are only possible after owner-approved commit and are mandatory before `FINALIZED`. A-05 replacement PRIMARY plus PWA acceptance remains cutover-only. Nonblocking audit observations about REC whitespace, stale planning counts, MVP restore attestation labeling, producer SHA allowlisting and incomplete failure-mode test enumeration remain tracked as Minor, not accepted production recovery proof.

**Independent B control-audit follow-up (2026-10-08):** the second auditor found two new integration Major findings on SHEDULLER `380c964d`, despite the earlier three fixes:
- **B04-R-01:** `.github/workflows/finalize-migration.yml` had pinned outdated HEALTH `c423d4a4`, bypassing the audited atomically locked finalizer. Fixed by [SHEDULLER PR #12](https://github.com/Alexio000/SHEDULLER/pull/12): checkout now pins independently tested HEALTH `ad04d6136178086a60ef47cd31dabbc83b71d6ff`; production workflow and CI check the actual checkout SHA and presence/use of `locked_finalization_sql`.
- **B04-R-02:** `restore_drill.verify_migrated_sources()` shadowed `source_manifest_path` with a Historical relative file path. Fixed in PR #12: separate `historical_relative` variable, positive exact locator check, and synthetic `publish_restore_evidence → get_private_evidence` consumer bridge with tampered locator rejected. CI `37825117450` PASS; merged as `0a06e0a7`.
- **Linked private finalization integration:** [SHEDULLER PR #13](https://github.com/Alexio000/SHEDULLER/pull/13), merged as `98e7d850709449f6b367c1752f78352725233458`, executes the actual private finalizer against disposable PostgreSQL 17 with scoped read-only backup fingerprint queries, actual evidence INSERT, authenticated-proof acceptance stub, and locked `COMMITTED_REGISTRY → VALIDATED → FINALIZED`. The test also mutates a medical row after private preflight, verifies finalization rejects it without state advancement, restores the synthetic record and verifies success (CI `37826365607` PASS). External Drive/GitHub transport is mocked in this particular PG test and verified separately by GitHub Actions synthetic artifact CI.
- These changes are **implementation fixes and synthetic integration evidence only**. No post-full-migration production restoration has occurred; the old Drive-native HealthDB remains canonical. Repeat independent B acceptance of new exact SHAs is still required before declaring technical GO. Cutover remains separately blocked by real full-set B-04 recovery and A-05/PWA/write-path criteria.

**Independent B acceptance of B-04 — 2026-10-08:** auditor B independently verified the exact frozen revisions HEALTH `6c0bb3959c459c9d693de21bd4fa4bb2639a3eea` and SHEDULLER `98e7d850709449f6b367c1752f78352725233458`, with the production workflow pinned to independently reviewed HEALTH runner `ad04d6136178086a60ef47cd31dabbc83b71d6ff`. Verdict **B-04 technical GO**, B04-R-01 and B04-R-02 **FIXED**, B04-B-01/B-02/B-03 **FIXED**, no new Critical/Major in this focused scope. The auditor confirmed exact checkout SHA guard, unchanged source manifest locator through the private proof chain, isolated PostgreSQL 17 private evidence INSERT and atomic 15-table locked FINALIZED with negative post-preflight mutation, complete Historical inventory guards, and CI SHEDULLER `37826507541` plus HEALTH `37826768417` PASS. The external Drive/GitHub calls and full production semantic verification in the PostgreSQL integration test are mocked, and no actual full production restore has happened; these limits remain explicit and are **not** new pre-migration technical blockers. Before execution, a **final independent read-only audit A on these exact revisions** must still confirm overall controlled migration readiness, single-writer/freeze, source provenance, authorization, RLS/Auth, rollback and remaining gates. Even if A returns GO, freeze/full migration requires a separate explicit owner authorization. Full operation-bound backup, independent 15-table + Historical original restore and authenticated proof must PASS after COMMITTED_REGISTRY and before FINALIZED. Replacement PRIMARY A-05/PWA acceptance and controlled write path remain separate cutover prerequisites.

The executable private recovery evidence contract, fail-closed finalization
workflow and remaining A-05 recovery/PWA acceptance are documented in
[SHEDULLER — B-04/A-05 audit recovery guide](https://github.com/Alexio000/SHEDULLER/blob/main/docs/AUDIT_B04_A05_RECOVERY.md)
(private; authorized maintainers only). This reference is part of the
pre-migration handoff, not a claim that a full-dataset recovery has run.

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

Historic passes are retained. Independent auditor B now accepts all five B-04 Major remediations and returns technical GO on the frozen revision pair. The final independent overall audit A and the owner's separate explicit full-migration authorization are still required before starting freeze or migration. This technical GO does not waive mandatory real post-commit independent recovery or the later cutover requirements. B-04 full-dataset backup/restore proof cannot be produced until after the separately authorized full migration commits; this proof is mandatory **before FINALIZED**, not a prerequisite to starting a controlled owner-authorized migration. No full migration or cutover is authorized.

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
