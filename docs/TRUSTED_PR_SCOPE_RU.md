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

## Writer-code candidate scope — 2026-10-14

A third proposed target, `writer-code`, is now included in the **draft-only** base-controlled PR scope policy. Its candidate test classification permits the narrow `scripts/writer/**`, `scripts/validation/**`, `db/**`, `supabase/**`, Writer-specific docs and the exact `.github/workflows/code-validation.yml`. **Every** Writer-code change requires author owner ID plus `WRITER-CONTROL: <exact-pr-head-sha>` as a line in the PR description. All other workflows, including `writer-authorization.yml` and `health-trusted-scope.yml`, are forbidden. Hidden files, symlinks, unsafe paths, credentials and foreign release train paths fail closed.

This is only a candidate scope filter, NOT independent clinical review, signed medical consent, a GitHub branch protection rule, or permission to release this Writer SHA. Owner-authored PR body text is a mutable intent marker, not a cryptographic grant.

### New security issue to resolve before acceptance

The current candidate runtime additionally requires `HEALTH_TRUSTED_POLICY_SHA == git HEAD == GITHUB_SHA`, where the last SHA is the default branch's base event SHA. This prevents a genuinely independent policy-pin lifecycle when `main` advances while Writer must remain pinned, unless the policy SHA is reaccepted. **Do not silently remove the equality check.** Independently review the precise trust chain for the workflow source on protected default `main`, fixed checked-out policy code, signed event metadata and final status issuer identity; implement/run real adversarial negative PRs before any Ruleset changes. A same-named GitHub Actions check is not proof of a distinct trusted workflow. Until that passes, Issue #50 and Writer-code trusted-check acceptance remain BLOCKED.

Writer-code is currently an inactive staging branch created at accepted `main` SHA. The production authorizer remains bound to `refs/heads/main` and accepted `github.sha`; neither it nor its broker/runtime policy was changed by this draft. The default-branch workflow itself can only be deployed during a separate authorized Writer/main exact-SHA acceptance. No GitHub Actions secrets, grants or production deployment are required for synthetic policy tests.

## Изолированный security-only кандидат — 14.10.2026

Этот компонент развивается отдельно от Scheduler launchers в security/trusted-pr-scope-20261014. Старый Draft PR #72 всё ещё содержит дубликат кандидата; до любого merge требуется дедупликация, чтобы не выпускать сценарии backup вместе с security scope.

### Два неизменяемых pin

- HEALTH_TRUSTED_POLICY_SHA — принятый полный commit SHA кода проверки; проверяемый файл исполняется только из этого commit.
- HEALTH_TRUSTED_WORKFLOW_BLOB_SHA — отдельно принятый Git blob SHA файла .github/workflows/health-trusted-scope.yml из default main. Это не commit SHA.
- Verifier читает metadata действующего файла через read-only GitHub Contents API для точного событийного GITHUB_SHA. Main может получить docs-only commit, не меняя принятый checker и workflow blob. Без любого из двух pin результат FAIL.
- Оба значения задаются лишь после review и owner acceptance; скрипт не выдает клинических разрешений, не вызывает backup, не использует Secrets и не исполняет файлы PR.

### Особенности GitHub.com 2026

С 08.12.2025 pull_request_target использует default branch как source/ref/SHA: https://github.blog/changelog/2025-11-07-actions-pull_request_target-and-environment-branch-protections-changes/
С 02.11.2026 GitHub начинает enforcing блокировки pull_request_target для публичных репозиториев без применимой Actions event policy: https://github.blog/changelog/2026-09-17-workflow-execution-protections-in-github-actions-generally-available/
Следовательно перед bootstrap требуется проверить Actions policy Insights; любое разрешение события должно быть строго ограничено этим доверенным workflow. Пока разрешений и настроек не меняли.

### Незакрытая HIGH #50

Accepted workflow blob pin не доказывает, что требуемый статус trusted-code-scope не будет подделан PR-кандидатом с таким же именем. GitHub Actions integration ID сам по себе недостаточен. Доверенный issuer и required Ruleset проверяются реальными негативными PR (spoof static/check, удаление проверки, запрещённый backend или Writer diff, symlink, rename, stale head, изменённый workflow blob, неправильный pin), а не только unit-тестом. Не делать merge до независимой рецензии.

### Локальная синтетическая проверка

python3 -m unittest discover -v -s scripts/validation -p test_trusted_pr_scope.py

Обычный CI может быть зелёным, даже когда конкретные scope-тесты не вызваны workflow. Перед release нужны фактические логи выполнения именно этих тестов, принятие main SHA, проверка Rulesets и отдельное разрешение владельца.
