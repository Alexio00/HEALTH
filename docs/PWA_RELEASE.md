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
   runs a **fresh** Pages deployment on a `pwa` push affecting `frontend/**`
   or the workflow. Alternatively select `pwa` under **Run workflow** to
   create a new run. Check that deployment concluded `success` and the run
   head branch is `pwa`. Do not use **Re-run job** after an artifact was
   already uploaded: the same run can then contain two `github-pages`
   artifacts and `deploy-pages` rejects the ambiguous upload.
4. Check browser-visible behavior under an authorized session. GitHub Pages
   deployment success is not itself a UI or clinical Writer smoke-test.
5. Recheck that `main` SHA and Supabase Writer accepted SHA have not moved.
   Do not use direct SQL updates to bypass Writer's accepted-code boundary.

The current Pages workflow still automatically deploys on `main` pushes
that touch `frontend/**` or the Pages workflow. This is a **known limit** of
the first-stage isolation: such a merge can overwrite the published `pwa`
assets. If it happens, start a **new** `pwa` workflow_dispatch deployment to
restore the exact approved `pwa` revision.
Never merge a Writer branch's frontend files into `main` on the assumption
that the Pages site will stay unchanged.

## Working with other open branches (inventory dated 2026-10-13)

**Re-check live PR state before acting; this is a coordination snapshot,
not standing permission to merge, rewrite or delete any branch.**

- PR #38, `frontend/vaccination-overview-20261013`: old `main` base;
  move to `pwa` only after preserving existing `app.js`, `styles.css`,
  `tests/contract.mjs`, `index.html`, OAuth test assets, and PWA cache
  behavior. Reconcile `frontend/README.md` too; retargeting alone is unsafe.
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

A frontend PR succeeds after clean comparison with `pwa`, green tests,
a new successful `pwa` Pages workflow run, and a browser smoke-test
(or explicitly recorded NOT_VERIFIED).

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
