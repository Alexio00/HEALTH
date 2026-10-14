# Независимый аудит доверенного PR scope-check HEALTH — задание для отдельного аудитора

**Статус:** только read-only independent review, без разрешения на merge, изменения Rulesets, Supabase, медицинскую запись или GitHub Actions deployment.

## Цель

Проверить, что доверенный scope-check действительно независим от кода PR и что обязательный GitHub Ruleset нельзя удовлетворить поддельным CI-статусом. Автор проекта не может считать собственную проверку независимой. Запрещено объявлять HIGH Issue #50 закрытым только по зелёному CI.

## Зафиксировать предмет и версии

- GitHub основной репозиторий Alexio00/HEALTH; отдельно SHEDULLER не изменять.
- Сначала прочитать приватные актуальные HealthDB Project State и Manual через разрешённый Drive; медицинские REC/Labs/Sources не открывать.
- Проверить фактический main SHA; на 14.10.2026 accepted SHA был 3409791f1ffc5749020e7ff07139b0cec722f6fc. Не полагаться на историческое значение без свежего readback.
- Прочитать полный diff Draft PR #78 (security/trusted-pr-scope-20261014), exact HEAD и все 4 файла.
- Прочитать связанные Draft PR #72 (Scheduler launchers), #76 (release trains), #35 (Writer), #73 (scheduler-code), Issue #50 и #69.
- Перепроверить активные GitHub Rulesets для main, pwa, writer-code, scheduler-code и списки bypass/checks. Не менять их.

## Чек-лист adversarial review

1. Источник workflow pull_request_target: проверить GitHub.com изменение 08.12.2025 (default main source/ref/SHA), event payload identity, repo/owner/ref и отказ при stale PR head/base.
2. Не исполняется ни один байт PR; нет checkout candidate или token write/secrets; в Python запрещены динамические SQL/Shell commands из PR. HEAD/BASE trees запрашиваются через GitHub API read-only с полнотой pagination и контролем symlink/mode.
3. Пара независимых pin: HEALTH_TRUSTED_POLICY_SHA — принятый commit кода; HEALTH_TRUSTED_WORKFLOW_BLOB_SHA — принятый blob default workflow. Проверить, что docs-only main advancement возможен при неизменном blob, а любой изменённый workflow/blob, неверный SHA, отсутствие var или ошибочный API response завершается отказом.
4. Оценить circular trust: изменённый авторизованным лицом main workflow может обойти локальную самопроверку. Указать, какая независимая GitHub/App/Ruleset/branch защита препятствует этому в реальном проекте. Не допускать ложного PASS.
5. Проверить моды pwa/scheduler-code/writer-code, контроль всех rename/from/to, удалений, скрытых файлов, symlink, secrets, произвольных workflows, forbidden Writer SQL и auth. Для Writer exact-head acknowledgement не является медицинским owner approval.
6. Проверить, способен ли PR создать GitHub Actions job с тем же check name и GitHub Actions integration_id=15368, чтобы обмануть требуемый статус. Отдельный источник check-run identity или механика, подтверждённая реальным негативным PR, обязательны.
7. Оценить GitHub.com событие: после 02.11.2026 pull_request_target для публичных репозиториев по умолчанию блокируется без точечной Actions event policy. Проверить текущие Insights и возможность узкого allow только trusted workflow, без глобальной политики.
8. Обнаружить дублированные файлы PR #78 и #72; дать точный план безопасной дедупликации, чтобы Security PR можно было принять без Scheduler launcher/backup Secrets.
9. При наличии локального разрешённого Python запустить python3 -m unittest discover -v -s scripts/validation -p test_trusted_pr_scope.py на точном checkout HEAD PR #78. Если Work не имеет локального компьютера, не имитировать результат; подготовить команды владельцу.
10. Негативный тест с реальными отдельными PR и проверка фактического merge blockage требуют отдельного разрешения владельца на GitHub writes. Read-only аудит может лишь предложить план; отсутствие evidence обязано сохранить статус BLOCKED.

## Ограничения и итоги

Формат ответа: exact PR SHA, verified ruleset IDs/conditions, SHA workflow source, независимая таблица findings severity+file/line, запущенные реальные проверки, что осталось непроверенным, оформленный rollback, итог INDEPENDENT_REVIEW_PASS/PARTIAL/FAIL. Не включать медицинские данные, repo secrets, GitHub tokens и приватные provider IDs.

**Приёмка:** PR #78 не сливать в main и не изменять принятый Writer SHA до отдельной owner-authorized процедуры accepted version; сохранить PWA static до доказанной защиты. Любой реальный rollout требует independent review и новых явных полномочий.

Документация: https://github.blog/changelog/2025-11-07-actions-pull_request_target-and-environment-branch-protections-changes/ ; https://github.blog/changelog/2026-09-17-workflow-execution-protections-in-github-actions-generally-available/ ; https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target
