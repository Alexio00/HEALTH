# PWA release isolation

See [AGENTS.md](../AGENTS.md) for mandatory branch routing, cross-PR
conflict resolution, safety boundaries and Writer acceptance rules. Read
live branches and open PRs at the start of each new development task.


**Production Writer:** accepted from `HEALTH/main`, with exact signed owner
authorization, accepted commit SHA in GitHub Actions variable, Supabase Edge
broker policy and `health_writer.runtime_policy.code_sha`. Nothing in this
document relaxes those checks.

**Frontend release:** `HEALTH/pwa` is a separate deployment source for
`Deploy HEALTH PWA`. Frontend PRs target `pwa`, not `main`. Merge
to `pwa` does **not** change the accepted Writer commit SHA. Do not dispatch
the clinical authorization workflow from `pwa`.

## Release procedure

1. Prepare and review only frontend UI/assets changes against `pwa`.
   Check that no Writer scripts, SQL schemas, Edge broker, or authorization
   workflows changed in the PR.
2. Obtain a green `HEALTH code validation` on the PR and exact merged `pwa`
   commit. The workflow covers both `pull_request` and `push` on `pwa`.
3. The `pwa` copy of `.github/workflows/deploy-pages.yml` automatically
   runs on a `pwa` push affecting `frontend/**` or the workflow. It uses
   concurrency group `pages-pwa` (independent from the legacy `main` group).
   A **Verify PWA before release** job checks frontend syntax, synthetic
   contracts, and the public secret-pattern guard, and uploads the exact
   checked Pages artifact. **Publish verified PWA** runs only after that job
   succeeds and can deploy only from `refs/heads/pwa`. This is a
   mandatory pre-deploy frontend gate, NOT a replacement for the full
   `HEALTH code validation` workflow run on a pull request.
   On a failed deployment, either re-run only the deploy job while its single
   valid artifact remains, or start a new workflow run from `pwa`.
   Do not re-run the artifact-uploading job or the entire workflow under the
   same run ID after an upload, because duplicate `github-pages` artifacts
   can make the deploy action fail.
4. Check the final postcheck job, exact release SHA and artifact file hashes.
   Then check browser-visible behavior under an authorized session. GitHub Pages
   deployment success is not itself a UI or clinical Writer smoke-test.
5. Recheck that `main` SHA and Supabase Writer accepted SHA have not moved.
   Do not use direct SQL updates to bypass Writer's accepted-code boundary.

The legacy Pages workflow still exists in `main`. The owner-restricted
Pages environment allows only `pwa`; do not relax this restriction. Removal
of the legacy workflow belongs to the separately accepted Writer update in PR #39. If it happens, start a **new** `pwa` workflow_dispatch deployment to
restore the exact approved `pwa` revision.
Never merge a Writer branch's frontend files into `main` on the assumption
that the Pages site will stay unchanged.

## Branch protection for `pwa` (repository setting)

The live branch reports `protected: true` on 2026-10-13.
Active Ruleset 25010980 requires PR, up-to-date base, and Actions `static`;
deletion and force-push are blocked and no bypass actors are configured.

The repository is publicly visible, so GitHub Free supports Rulesets/branch
protection without upgrading. The connected GitHub integration cannot modify
administration settings (the protection read API returned 403). The owner configured this in GitHub **Settings → Rules → Rulesets** (or **Branches →
Add branch protection rule**):

- Target only branch `pwa`, set ruleset to **Active**, do not include
  `main` or Writer's other refs.
- **Require a pull request before merging**, **Require status checks to pass**,
  selecting exactly the `static` job from `HEALTH code validation`, and
  **Require branches to be up to date before merging**.
- Block force pushes and deletions; disallow bypasses where available.
- With a sole maintainer, do not require another human approval until a
  second reviewer exists. A required self-review could deadlock all UI PRs.
- Do **not** require the `github-pages` deployment as a *pre-merge* check:
  publishing must happen after merge, or PRs deadlock.

The `pwa` code-validation workflow now runs for **every** PR targeting
`pwa`, including workflow-only and root-level instruction changes, so
the mandatory `static` status is available. Verify `pwa` reports
`protected: true` after saving the rules. A clean PR CI and an actual
merged `pwa` release are separate checks.

The owner has limited the `github-pages` deployment environment to
`pwa`, so `main` cannot publish even though its old workflow still exists.
The `pwa` workflow additionally refuses non-`pwa` refs.

## Working with other open branches (inventory dated 2026-10-13)

**Re-check live PR state before acting; this is a coordination snapshot,
not standing permission to merge, rewrite or delete any branch.**

- PR #38 (Vaccination) was merged into `pwa` on 2026-10-13. Future
  frontend changes must preserve vaccination module and automatic SHA-bound shell cache, plus previously merged UI changes.
- PR #36, `feature/supabase-test-consent-ui-20261013`: its four
  `frontend/oauth-test/*` files are **already present** in `pwa`, preserved
  from an earlier static Pages deployment. Do not merge the same assets
  into `main` merely to publish them. Any genuinely new consent/auth flow
  requires separate review of its threat model.
- PR #35, `feature/chat-writer-contract-20261013`: Writer/backend and
  `code-validation.yml`, so its final acceptance belongs in `main`
  under the existing exact-SHA protocol. Do not accidentally remove
  `pwa` CI triggers when syncing workflows.
- PR #33, `maintenance/ru-governance-legacy-independence-20261013`:
  touches Writer, governance and `frontend/README.md`; split or explicitly
  reconcile the cross-branch scope before acceptance. Do not overwrite
  this `pwa` release policy with a stale README.
- PR #27, `migration/planned-medication-status`: SQL migration plus old
  migration tooling; requires fresh applicability and security review
  against the **live** Supabase canonical system before any use.
  Never treat old migration code as an implicit production fix.
- PR #22, `test/nonmutating-probe-handoff`: docs-only; still changes
  Writer's accepted `main` SHA if merged there. Batch with a separately
  authorized main acceptance or defer.

Orphaned/historical branches include `maintenance/pwa-ui-refine-20261007`,
`maintenance/frontend-accordion-medrec-visits-20261013`, and
`release/pages-ui-20261013-preserve-oauth-test`. New work starts from
the **live** `pwa` or `main`, not an old release branch. Do not delete
old branches without the owner's decision.

### Two kinds of acceptance

A frontend PR may be accepted only after full 40-character BASE_SHA and
HEAD_SHA plus exact diff are frozen, independently reviewed for compatibility,
security, negative tests and rollback, and explicitly approved by the owner
for that exact SHA. Immediately before merge, recheck unchanged HEAD/BASE,
the complete diff, unresolved threads, current Ruleset and green required
`static`. Any candidate change voids the earlier acceptance. After an
authorized merge, verify the exact `pwa` release SHA, a new successful
Pages deployment with a verified pre-deploy gate and postcheck, then perform
an authorized-session browser smoke-test (or explicitly record NOT_VERIFIED).
A successful CI run is never independent review or owner GO.

A Writer PR requires current, independently reviewed code, exact `main`
SHA reacceptance in the GitHub owner policy, Edge broker and runtime,
and a verified restricted-role behavior check. A `pwa` merge does not
authorize a clinical operation. Never silently replace a missing private
Writer operator with administrative Supabase SQL.

## Scope / future

- `pwa` retains the already deployed `frontend/oauth-test/*` assets; merging
  UI changes must not silently remove them.
- Parallel Writer work stays on its original branches, and `main` remains
  its exact signed authorization ref.
- Long-term complete isolation needs a separately accepted, immutable Writer
  ref/repository and removal of the `main` frontend auto-deploy path.
  That transition changes the trust contract and needs an independent audit,
  a one-time coordinated reaccept and explicit owner approval.
- This `pwa` solution avoids that Writer migration for normal UI-only PRs.

## Trusted PR scope and release-control review

Ordinary PRs may change regular files in frontend/ and only AGENTS.md or
docs/PWA_RELEASE.md outside it. Backend, SQL, private paths and symlinks fail.
Release controls (frontend/release/ and the named PWA workflow files)
require a PR authored by owner ID 308028794 and the exact standalone body line
`PWA-RELEASE-CONTROL: <40-character head SHA>`. A new head invalidates it.
This is explicit review of an authorized technical release; never add the line
to an unknown PR merely to obtain PASS.

The static job loads scope logic from protected base objects, not PR code.
The attempted standalone pull_request_target workflow did not run: GitHub now
loads it from the default branch, which is main and remains pinned. It is
removed from pwa rather than represented as active protection.
The static step executes base scope code and reads candidate Git objects.
Changes to code-validation.yml outside its frontend-check block are forbidden,
even in a release-control PR. Writer/OIDC checks must remain byte-for-byte.

**Limit:** the current required Ruleset binds the name static to GitHub Actions,
not an immutable workflow identity. A malicious PR could invent another Actions
job with that name. There is no independently enforced pwa-scope check. This is defense in
depth and a release-review gate, not an unbypassable hostile-contributor boundary.
Strict protection needs an independently enforced required workflow/status
issuer or an additional suitable repository rule, reviewed by the owner.
Do not weaken Rulesets to bootstrap this. Initial policy PR is independently
reviewed against baseline 93964e3524171d789f03608958a6b0740bae23ee.

## Static-only offline boundary

The worker caches only eight enumerated public shell resources. Every query
string, OAuth test page, API, arbitrary path, authorization/range request,
redirect, non-200, wrong MIME and private/no-store/no-cache response is excluded.
Old health-shell caches are purged on activation; unrelated caches are retained.
Offline shell availability never means offline medical data: Supabase responses
are not stored in CacheStorage. OAuth test consent requires network access.

## Exact artifact and post-deploy acceptance

The build runs only with GitHub Actions GITHUB_REF=refs/heads/pwa and
GITHUB_SHA equal to the checked-out Git HEAD. It copies fifteen enumerated
runtime files into a new runner-temp artifact, stamps index.html and sw.js,
then generates release.json (schema 1, exact sha, SHA-256 for every runtime file).
Tests, release tooling, READMEs and RELEASE_CHECK.md are not published.
The footer shows the short SHA of that HTML artifact, not the live marker of
a newer release.

The worker uses health-shell-<full SHA>. Installation fetches all eight shell
files with redirect:error and validates MIME/cache policy and generated byte
hashes before storing any of them or calling skipWaiting. Existing cached
shell responses stay within one release. Activation removes old health-shell
caches and claims clients; a controlled page reloads once on controllerchange.
updateViaCache:none avoids relying on the browser HTTP cache for worker updates.
A stale CDN file fails installation; the previously installed worker continues.
Hash routes use the same index.html. OAuth/API/query requests remain uncached.

Verify published release bytes runs after deployment in the same workflow.
It requests root, release.json and all fifteen runtime files using no-store,
checks status/MIME/exact SHA/byte hashes, and retries at most twelve times
(10 seconds between attempts, 10-second request timeout, 5-minute job timeout).
It never has continue-on-error. A FAIL makes the whole release workflow FAIL
even if Publish verified PWA succeeded. GitHub Pages may already show the bad
release: the postcheck detects it, but is not an atomic deployment rollback.
Actions failure notifications/run status are the signal; no paid service.
A matching old marker without matching files is a failure.
HTTP PASS does not verify authenticated clinical UI or an installed device.

## Rollback through a protected PR

1. Select a previously verified pwa commit and inspect its release/evidence.
2. Fetch current pwa and create a fresh rollback branch from it. Never reset
   the remote ref or force-push. Preserve release controls and current tooling.
3. Revert only the faulty frontend change (for a merge: git revert -m 1 <SHA>),
   resolving conflicts against current routing, OAuth assets and release policy.
   If reverting would remove the safe worker/build pipeline, restore only
   affected UI files from the known-good tree instead. Rebuild with current
   tooling; do not copy the old release.json or generated worker.
4. Review the complete diff; create PR to pwa. Any release-control edits need
   owner PR with the exact-head PWA-RELEASE-CONTROL line. Mandatory static
   with its base-sourced scope step must pass with current base. No rules bypass.
5. Merge normally. New merge SHA is a new release identity, including cache.
6. Wait for Verify/Publish/postcheck, compare actual marker SHA and all bytes.
   Inspect unauthenticated interface first; authorized clinical checks only
   in separately permitted sessions. Preserve synthetic offline route tests.
7. A failed install retains the old worker. A successful rollback install
   switches cache and reloads controlled pages; if needed close/reopen the PWA
   to trigger update. Do not clear medical browser storage indiscriminately.
8. If postcheck or rollback fails, keep its evidence, stop further unrelated
   releases, identify CDN/asset/build failure and make another normal repair
   PR from live pwa. Re-run only deploy/postcheck when appropriate; never
   re-upload duplicate github-pages artifacts under the same run ID.

The release regression suite builds two synthetic SHA releases, verifies that
the worker/index identities change, simulates stale files and failed installation
(no partial cache activation), retries with a finite bound and confirms recovery
to a complete shell. No production rollback is performed by this task.

Standalone trusted workflow activation would require an independently authorized
default-branch change/Writer acceptance, or a separately controlled external
check issuer. The current task performs neither. Do not add a non-existent check
to the Ruleset: that would deadlock PRs. GitHub reference:
https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target

## Независимость от большого обновления Writer — контроль на 14.10.2026

PWA-only функциональность на **существующем** read-only контракте можно продолжать и выпускать через `pwa` независимо от нового Writer. При этом безопасность не выводится из места размещения файла: изменения OAuth/consent, Supabase-client, service worker, релизного скрипта и GitHub Actions требуют отдельного threat-review, а issue [#50](https://github.com/Alexio00/HEALTH/issues/50) остаётся незакрытым HIGH. Новая медицинская запись, новая writable схема или статусы вакцинации относятся к `WRITER_IMPACT` ([#62](https://github.com/Alexio00/HEALTH/issues/62)) и **не должны** активироваться на PWA до соответствующего принятия bounded Writer/Verifier/Validation и независимого readback. PR [#51](https://github.com/Alexio00/HEALTH/pull/51) и [#59](https://github.com/Alexio00/HEALTH/pull/59) требуют выделения отдельно выпускаемой визуальной части, если зависимости новых медицинских сущностей нельзя исключить.

Имеется staging ветка `writer-code` для будущего независимого релиза Writer, но она **не исполняется и не принимается** автоматически. Производственный Writer по-прежнему привязан к exact `main` SHA до security-acceptance новой модели. Исполняемый Scheduler отдельно готовится в `scheduler-code` (#73), а launchers в default main (#72) требуют отдельного окна. PWA CI/release не должны триггерить Writer authorizer, GitHub dispatch или backup, и не получают клинических credentials.

Подробный дизайн — [Draft PR #76](https://github.com/Alexio00/HEALTH/pull/76). Этот раздел применим только как инструкция PWA-разработки, не как разрешение на Writer/main merge или смену авторизации.
