# Trusted GitHub PR scope (Draft; do not enable yet)

This is a **candidate** for one base-controlled, read-only scope verifier for
\`pwa\` (Issue #50) and \`scheduler-code\` (Issue #65, H-01). It does not change
accepted Writer/main until separate exact-SHA acceptance.

- Uses \`pull_request_target\` from the base repository, with \`contents:read\`
  and \`pull-requests:read\` and **no repository Secrets, write token, execution,
  checkout or dependencies from the PR**.
- Pins the policy checkout to the separately accepted immutable
  \`HEALTH_TRUSTED_POLICY_SHA\` value. A random branch ancestry is not acceptance.
- Reads current GitHub PR metadata, all PR filenames, renames, deletions and
  commit trees via read-only APIs. Rejects stale head/base, mismatched inventory,
  symlinks, forbidden backend paths, unsafe metadata, workflow controls without
  owner ID + exact HEAD acknowledgement. PWA's existing \`static\` stays mandatory.
- Workflow source identity and status name must be validated empirically with
  real positive and negative PRs. The GitHub Actions App \`integration_id\` by
  itself does **not** distinguish a trusted workflow from a candidate-owned job
  using the same name. Do not change required Rulesets until spoof checks PASS.
- GitHub's public-repository default policy is scheduled to block
  \`pull_request_target\` on 2026-11-02. An explicit *applicable* allow event
  policy might be needed; check repository Actions policy and runtime before
  any rollout. An ordinary PR check is not a substitute for a trusted issuer.
- Since the new workflow runs only after \`main\` acceptance, no actual trusted
  runtime check is possible from the Draft alone; synthetic CI only validates
  pure scope logic. **No automatic or unapproved Writer SHA change.**

Sources:
https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target
https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks

Release tests before rule change: normal PWA PR, forbidden Writer/SQL, deleted
guard call, self-named fake check, scheduler normal PR, scheduler forbidden
workflow, stale HEAD; verify actual check run source/commit and merge protection.
If the fake-check negative test cannot prove tamper resistance, mark H-01/#50
as **not solved** and use separate verified owner policy instead of claiming PASS.
