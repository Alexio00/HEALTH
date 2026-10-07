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

Current verdict: **NO-GO**.

Resolved during the rerun:
- source-freeze/package contract mismatch fixed and then strengthened so the sealed package fingerprint binds freeze/capture control metadata; latest hardening commit `89bbaa0882330016c623090559301cc952694313`;
- code validation run `37685406167` PASS;
- live Auth invariants PASS;
- live browser/database security invariants PASS;
- scheduler hardened database -> Sources -> verification chain PASS;
- schema migration ledger matches the nine canonical timestamped migration files.

Remaining blocker:
- the hardened five-file database backup format now includes `supabase_migrations` schema/data, but a **real isolated restore drill** has not yet passed after that backup-format/tooling change. The private scheduler now runs that drill against a fresh local Supabase stack; checksum/round-trip verification remains PASS but is not a restore.

Full migration remains forbidden until that restore drill passes and the final audit is rerun to PASS.

## Non-blocking advisor status

- Technical public tables intentionally have RLS with no browser policies.
- Leaked-password protection is unavailable on the current Free plan.
- Newly created covering indexes can remain reported as unused until traffic exercises them.

## Full-migration gate

Full migration remains forbidden until:
- hardened scheduler execution test PASS;
- remaining owner gates resolved;
- final pre-migration audit PASS;
- explicit owner authorization.

Cutover remains a separate later owner decision.
