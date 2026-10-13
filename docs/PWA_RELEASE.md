# PWA release isolation

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
3. On the existing workflow `.github/workflows/deploy-pages.yml` (which is
   registered on default branch `main`), choose **Run workflow**, select
   **pwa**, and manually dispatch. Verify the deployment conclusion is success.
4. Check browser-visible behavior under an authorized session. GitHub Pages
   deployment success is not itself a UI or clinical Writer smoke-test.
5. Recheck that `main` SHA and Supabase Writer accepted SHA have not moved.
   Do not use direct SQL updates to bypass Writer's accepted-code boundary.

The current Pages workflow still automatically deploys on `main` pushes
that touch `frontend/**` or the Pages workflow. This is a **known limit** of
the first-stage isolation: such a merge can overwrite the published `pwa`
assets. If it happens, manually redeploy the exact approved `pwa` revision.
Never merge a Writer branch's frontend files into `main` on the assumption
that the Pages site will stay unchanged.

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
