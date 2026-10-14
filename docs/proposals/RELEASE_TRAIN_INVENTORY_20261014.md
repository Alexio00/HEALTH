# HEALTH — release-train inventory and cross-PR disposition (14.10.2026)

> **POINT-IN-TIME TECHNICAL INVENTORY / DRAFT ONLY.** Not a governing policy, production release, security gate, approval, or clinical authorization. Live private Project State / Project Manual override this snapshot. Re-read all SHA, PR heads, review threads, CI, GitHub rulesets and runtime before decisions. No patient data or credentials included.
>
> This document is a short-lived coordination input for [PR #76](../../pull/76), [Issue #69](../../issues/69), [Issue #62](../../issues/62), [Issue #65](../../issues/65), and [HIGH #50](../../issues/50). Close/archive this snapshot after incorporating accepted conclusions into governing technical docs; do not create a second permanent policy.

## Verified source state

- Repository: `Alexio00/HEALTH` (public). Read-only GitHub branch/ruleset/PR API and private governing State/Manual inspected on 14.10.2026.
- `main` = **accepted production Writer code pin** `3409791f1ffc5749020e7ff07139b0cec722f6fc`. Signed owner authorization and accepted runtime/broker pin remain required. **Any main merge changes the pinned main commit and requires coordinated Writer reacceptance** under today's workflow. Do not merge docs-only changes to main opportunistically.
- `writer-code` = `3409791f1ffc5749020e7ff07139b0cec722f6fc` (development only); `pwa` = `fbc901eb0ebeba322d73969a327cc86cfc7e916b`; `scheduler-code` = `3409791f1ffc5749020e7ff07139b0cec722f6fc` (candidate in PR #73, not merged); `scheduler` = `98f9c41ff9b1496dfc40d0da960971ae7bf58a42` (heartbeat only).
- Active, no-bypass Rulesets: `main` 25010398 (PR, no required check), `pwa` 25010980 (PR + required Actions `static`, integration 15368), `scheduler-code` 25029979 (PR, no required check), **`writer-code` 25071720 (PR and review-thread resolution; no required check)**. All disallow deletion/non-fast-forward. No rule protects heartbeat-only `scheduler`.
- **Correction needed in the existing Draft #76 proposal**: its table saying `writer-code` is unprotected / Ruleset absent is now stale. The applicable Ruleset was created later. Protection is not independent required trusted issuer. Likewise, open Issue #69 describes an abandoned option without `scheduler-code`: later owner-approved five-branch design supersedes that sentence; preserve issue history but reconcile the current acceptance criteria.
- Project State reports canonical Supabase ACTIVE and Writer enabled. Source originals live on Drive; historical records/Registry are read-only. The *current* full backup runs in private `Alexio000/SHEDULLER`; HEALTH in-repo Scheduler is **not** production. No live Supabase or GitHub Pages Environment readback was attempted as evidence of a new release.

## Release trains and dispositions

| Train | In-flight candidate | Current disposition | Acceptance destination |
|---|---|---|---|
| PWA UI | #51 (`pwa`) | Frontend-only Rv presentation, isolated from schema release | `pwa`, manually reviewed exact SHA, `static`, Pages postcheck |
| PWA UI | #59 (stacked on #51 branch) | Combined-vaccine display; reader/schema assumptions unresolved | Rebase/retarget only after #51 and #45 contract, then `pwa` |
| PWA docs | #77 (`pwa`) | Draft docs release-policy alignment | `pwa`, preserve live workflow and `static` |
| Writer Gateway | #35 (`writer-code`) | Synthetic envelope/status contract, not deployed OAuth/MCP gateway | `writer-code` development; production requires separate immutable Writer release |
| Vaccination schema | #45 (`main`) | Non-executable SQL proposals only, **WRITER_IMPACT** | Co-designed schema/Writer/Verifier/Validation/read API; no schema deploy |
| Scheduler executable | #73 (`scheduler-code`) | Consolidates #70/#71, synthetic tests; no production workflow | `scheduler-code` exact-SHA acceptance, independent security/restore review |
| Scheduler launchers | #72 (`main`) | Five default-main workflows only, disabled/unaccepted | main coordinated Writer release window + strict cutover/recovery |
| Release architecture | #76 (`main`) | Design and advisory scope classifier, not trusted security enforcement | main release window; reconcile stale Ruleset table first |
| Main/Pages policy | #39 (`main`) | Draft to remove old main Pages trigger and update routing | main coordinated Writer release window; postrelease PWA dispatch |
| Trusted PR scope | #78 (`main`) | **PAUSED: R3 CODE_FIX_FAIL / SECURITY_RELEASE_NO-GO** | No rollout or merge; HIGH #50 remains OPEN |
| Main docs | #60 (`main`) | Russian docs/navigation Draft | Future controlled main window |
| Mixed governance/code | #33 (`main`) | Documentation, Writer Source env changes and frontend overlap | Split/reconcile per domain, independent evidence, main window |
| Historical/test docs | #22 (`main`) | Older non-mutating Docker evidence, no active cutover | Preserve as history; merge only if current purpose established |
| Historical migration | #27 (`main`) | Planned medication schema already reflected in live DB; do **not** rerun migration | Preserve runner provenance; decide retirement after code comparison |
| Already integrated UI | #36 (`main`) | OAuth-test assets already in `pwa` (per PR description and PWA docs); not an active release | Verify exact blobs before owner-approved close, do not merge in main |
| Superseded Scheduler | #64, #67, #70, #71 | Old combined/duplicating candidates; #73 + #72 are the split design | Archive/close only after owner-approved diff-based confirmation |

All **19 open PRs** are represented in this snapshot. "Superseded" is a recommendation, **not** an executed close or proof of byte-identical implementation. All PRs remained open during this inventory.

## Dependency contract: writer, DB, PWA, Scheduler

1. `PWA_ONLY`: frontend display on existing Supabase reader contract; no direct DML, Writer keys, browser Secrets, or admin SQL. Independent `pwa` release is possible with actual Ruleset checks, manual independent review, browser/Pages readback and rollback.
2. `READ_SCHEMA_ONLY`: indexes/read-only views/API can be developed independently **only after** checking RLS/read grants, query compatibility and demonstrating no influence on clinical delta, Writer before/after checkpoint, and Validation.
3. `WRITER_IMPACT`: any medical writable table/column/FK/constraint/status, Source/REC/case/lab/plan relation, trigger or RPC envelope. Requires **one shared approved contract** covering Supabase migration, Writer allowlists/complete INSERT shape, locking/ID reservations, verifier receipts, Validation, RLS, backward compatibility, rollback and PWA readers. See Issue #62. No independently merged clinical schema.
4. Scheduler executable is separate from `main` launchers. Backend cron must originate from trusted default `main`; executor must be exact accepted immutable `scheduler-code` SHA. Separate backup and Writer scheduling is not a new medical writer. Shared DB/Source backup exclusion and complete actual restore remain hard gates. Old SHEDULLER must not coexist in rotation with new HEALTH candidate.
5. The `scheduler` branch is exclusively service heartbeat commits; never merge it into another branch. Its activity does not prove GitHub's scheduled workflow will never become disabled.
6. A **manual independent exact-HEAD/BASE SHA acceptance** was approved on 14.10.2026 for technical release work. It is **not a GitHub Security Rule**, not a bound OIDC issuer, and not a cryptographic owner consent for clinical writes. HIGH #50 stays open. `static` by GitHub Actions does not prove that PR-controlled policy cannot be bypassed.

## Small gates, ownership and ordering

| Gate | Owner / independent reviewer | Evidence required | Does not authorize |
|---|---|---|---|
| A. Align release inventory and freeze each PR | Architecture coordinator; Product Owner approves priorities | BASE+HEAD 40-char SHA, changed paths/diff, inter-PR conflicts, live Rulesets | Main merge |
| B. Frontend-only PWA release | PWA developer; separate reviewer; owner GO | PWA-only scope, passing existing `static`, postmerge artifact/SHA, browser validation, rollback | Clinical schema |
| C. Gateway contract candidate | Writer developer; independent security reviewer; owner development GO | Exact SHA, synthetic negatives, owner identity / replay / fail-closed review | Production Writer activation |
| D. Scheduler executable candidate | Scheduler Code developer; independent security and recovery reviewer; owner GO | Exact SHA and diff, synthetic faults, no secret/medical data in public repo, restore evidence | Backup cutover |
| E. Shared schema proposal (#45) | Architecture + Writer + PWA owners; independent verifier; owner approves contract | Explicit diff/impact matrix and compatible tests on disposable DB; source/clinical semantics kept private | Production SQL |
| F. Controlled `main` acceptance | Product Owner; independent reviewer; Writer operational owner | Exact main diff, accepted Writer pin/broker/runtime agreement, negative tests, release/rollback | Clinical data operation itself |
| G. Scheduler cutover | Product Owner; Scheduler Code owner; independent restore auditor | Last legacy ACTIVE readback; legacy paused and idle; new complete archive + actual private restore; no dual rotation; controlled follow-up runs | Deletion of old backups/project |

**Order recommendation:** keep PWA-only and isolated Writer/Scheduler candidate development parallel; settle shared schema #45/#62 before vaccine UI wiring; qualify #73 before #72; schedule a single minimal main acceptance window for accepted launchers/policy changes only after Writer security impact assessment. Do not use failed #78 to justify lowering existing checks.

## Stale documentation / cleanup decisions

- #76 live proposal inaccurately states `writer-code` lacks protection; update its candidate in its own branch by its owner before exact-SHA review, not by editing it from this PR.
- Issue #69 retains superseded branch decision; leave historical discussion intact, reconcile current criteria to five branches at owner-approved triage.
- Current private Manual contains a later section titled "18. Procedure ..." after the earlier sections 18 and 19. Treat the **heading title and owner decision date** as the authoritative reference until owner approves a numbering correction; this proposal does not edit the private Manual.
- #36/#27 and #64/#67/#70/#71 appear archival/superseded. Verify exact content and owners before proposing closure. No PR closed or branch deleted in this task.
- PWA `AGENTS.md` and open #77 may reference older Writer routing. Reconcile in the respective component's PR; do not force one component's docs onto another.
- This snapshot is an inventory, not a replacement for [Project State](https://docs.google.com/document/d/1eEZeDWhXw0h3PiVlc6xdGcVBQR0WvMVTgv50vMcGHU4/edit) or [Project Manual](https://docs.google.com/document/d/1Q_ZJ8_QffQUaOLXOSuho0FqPoXWGtHDBPVyBw8MVO90/edit).

**No cross-component writes, Secrets, production SQL, backup rotation, deployments, merges or approvals were performed for this proposal.**
