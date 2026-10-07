# Project State

Status: PRE-MIGRATION HARDENING; MVP operational acceptance PASS; full migration NOT authorized

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

- Live Auth invariants: PASS after hardening.
- Live browser/database security invariants: PASS after hardening.
- Public code CI synthetic migration package seal/verify: PASS.
- Hardened private scheduler execution test: PASS (revision 6). Database backup, Sources copy, database/source verification and five-file database round-trip SHA-256 all PASS.

## Owner gates

1. **Supabase region** — RESOLVED: owner explicitly accepted the existing `us-west-1` project; no region migration is requested before full migration.
2. **Supabase Auth dashboard** — RESOLVED by prior owner confirmation: public self-signup/new-user creation and anonymous sign-ins were disabled; subsequent hardening did not modify Auth dashboard configuration.
3. **Public Git commit email privacy** — RESOLVED: owner accepts the existing public commit-history email exposure and does not want history rewritten.
4. **Post-hardening PWA smoke** — PASS by owner: login succeeded and multiple records/pages were checked after first-party Auth-client hardening.

## Final pre-migration audit

Current verdict: **PASS**.

Final evidence:
- owner gates resolved: keep `us-west-1`; existing public Git commit email accepted; post-hardening PWA smoke PASS;
- source-freeze/package contract hardened so the sealed package fingerprint binds freeze/capture control metadata; hardening commit `89bbaa0882330016c623090559301cc952694313`;
- live migration ledger and public timestamped migration SQL are exact 9/9 after drift repair commit `3c72cbd950836ce3086b75d2ceaaed8b1527d89d`;
- full-migration runner has one fail-closed execute path requiring both the matching old-HealthDB freeze operation ID and literal owner token `FULL_MIGRATION_AUTHORIZED`, chaining seal/verify/stage/exact compare/guarded commit/exact public compare; hardening commit `46af6eef8b3dae0000c48b49f53fd216ae0d4957`;
- browser/database security validation is search-path invariant; commit `e63a40f1326a9e8628c0aaa7b5df2c04abc1cb95`, code validation run `37690027154` PASS;
- live Auth invariants PASS and live browser/database security invariants PASS;
- GitHub Actions in HEALTH and SHEDULLER use immutable full-SHA external action refs; no floating external action refs remain;
- hardened scheduler database -> Sources -> verification chain run `37676153947` PASS;
- real isolated five-file restore drill run `37690089948` SUCCESS: backup SHA-256 PASS, fresh local Supabase restore PASS, exact 15-table medical-domain comparison PASS, migration history 9/9 PASS, replacement-owner Auth recovery PASS, restored Auth/security invariants PASS, and restored record/source integrity PASS;
- current remediation validation stamps `PRE_MIGRATION_HARDENED_RESTORE` and `PRE_MIGRATION_FINAL_AUDIT` are PASS.

No pre-migration technical blocker remains from this remediation.

**Full migration remains forbidden until the owner gives a separate explicit authorization.** Cutover remains a later, separate owner decision.

## Non-blocking advisor status

- Technical public tables intentionally have RLS with no browser policies.
- Leaked-password protection is unavailable on the current Free plan.
- Newly created covering indexes can remain reported as unused until traffic exercises them.

## Full-migration gate

Pre-migration hardening and independent audit are PASS.

Full migration may begin only after a **separate explicit owner authorization**. The runner still requires the literal `FULL_MIGRATION_AUTHORIZED` token and the matching old-HealthDB PREPARED freeze operation ID at execution time.

Before any full migration commit, capture a fresh frozen Drive-native snapshot and revalidate the source freeze. The old Drive-native HealthDB remains canonical until a later explicit cutover authorization.

Cutover remains a separate owner decision and is not authorized by pre-migration audit PASS.
