# Writer — предложение независимого pinned-release trust (не внедрено)

**14.10.2026 — SECURITY DESIGN ONLY.** Этот документ описывает, как снять зависимость принятого Writer от двигающегося `main` без отключения проверки владельца. Ни новый workflow, ни broker/RPC, ни Supabase policy не развернуты; код production Writer и его accepted SHA остаются прежними.

## Действующая зависимость, которую нужно заменить

Сейчас `.github/workflows/writer-authorization.yml` исполняется из default `main` и требует `github.actor_id=308028794`, `github.ref=refs/heads/main`, `vars.HEALTH_WRITER_ACCEPTED_SHA == github.sha`. Скрипт `scripts/writer/signed_canonical_authorization.py` повторяет `GITHUB_SHA == expected_sha`; подписанный GitHub JWT проверяется ограниченным Supabase broker. Приватный `health_writer.runtime_policy.code_sha` привязан к точному accepted code SHA. Поэтому docs-only merge в `main` отрывает исполнение от допуска.

**Не менять это условие на `true`, не удалять `ref/main`, не доверять app token, GitHub API HTTP 204, зелёному CI или непроверенному body PR.**

## Безопасная целевая схема (единственный Writer)

1. **Control plane:** `main` сохраняет минимальный доверенный workflow, запускаемый только проверенным GitHub owner и с read-only checkout. Его source/identity должны подтверждаться отдельным accepted workflow policy (например, exact verified blob digest при authenticated GitHub API readback). Одного `workflow_ref@refs/heads/main` без проверки содержимого недостаточно, потому что `main` меняется.
2. **Executable Writer:** `writer-code` только для разработки; после независимого review выпускается **полный immutable commit SHA** `accepted_writer_release_sha`. Запуск через reusable workflow `ORG/REPO/.github/workflows/writer-release.yml@<40-hex SHA>` либо другое строго привязанное immutable execution. Ссылки на moving `writer-code` HEAD, mutable tag или workflow PR запрещены. Одна и та же ограниченная implementation и отдельный verifier, не параллельные Writer.
3. **Signed proof:** broker сам проверяет GitHub JWKS/OIDC RS256: `iss`, точную аудиторию, `repository_id`, `repository_owner_id`, `actor_id`, `event_name=workflow_dispatch`, caller `ref`, expected `workflow_ref`, immutable called `job_workflow_ref` и `job_workflow_sha` (лишь при реальном reusable job), запрошенные `request_key/kind/digest` и отдельную привязку signed receipt к кандидату/nonce. Данные запроса не становятся доказательством подписи, если исходят лишь из input.
4. **Два раздельных pin:** `trusted_launcher_policy_digest` для default control workflow и `accepted_writer_release_sha` для исполняемого кода. Изменение `main` не должно молча менять ни один pin; изменение любого pin требует отдельного owner-signed change-control и независимого актуального readback broker/runtime.
5. **Backup/Source single-writer:** сохранить SQL exclusion, independent semantic/source receipt и воспроизводимый restore. Не создавать вторую альтернативную медицинскую запись либо SQL административный fallback.

### Что GitHub реально обещает, а что требуется доказать

В официальной документации GitHub `job_workflow_ref` и `job_workflow_sha` относятся к **jobs из reusable workflows**. Текущий production authorization workflow таким не является, поэтому нельзя требовать эти claims от сегодняшнего токена. GitHub разрешает ссылку `uses: owner/repo/.github/workflows/file.yml@<full-SHA>`; использовать SHA безопаснее moving ref. `workflow_sha`/event `sha` могут относиться к caller commit `main`, и это **не** прямое свидетельство проверенного executable Writer SHA.

Документация: https://docs.github.com/en/actions/reference/security/oidc ; https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows ; https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows

## Верификация перед любым production переключением

- Фиксировать exact workflow YAML hash из доверенного `main` и exact reusable workflow commit и сравнить с signed claims независимым private broker, а не из environment/job body.
- Отдельно проверить OIDC audience/issuer, owner/repo identity и session, подпись JWT/JWKS, время, token replay/JTI, run_id+run_attempt; действующий Writer contract с nonce/digest/consent.
- Синтетический **положительный** сценарий: harmless docs-only commit в `main` при неизменном trusted workflow blob и immutable Writer release должен не менять принятый Writer executable (но только после отдельной принятой новой release policy).
- **Отрицательные:** wrong actor/repo, workflow issuer spoof, modified default launcher blob, missing/forged job_workflow_ref, mutable Writer ref, wrong SHA, unaccepted schema, expired consent, wrong digest, stale nonce, API unknown response, repeated dispatch/receipt, failed verifier, replacement of trusted required check by same-name candidate job. Любой отказ оставляет Writer fail closed.
- Отдельные protected branch Rulesets для `writer-code` и `scheduler-code` после реальной проверки identities check issuer; доверенный `main` — только owner-controlled, с учётом HIGH #50.
- После code review и positive/negative hosted **HEALTH-TEST** теста: отдельно согласованный production cutover (broker, runtime policy, GitHub variable, rollback/backup) с accepted SHA и owner sign-off. До этого фиксированный `main` остаётся источником Writer-authorizer.

## Результат / следующая работа

Артефакт архитектурной рецензии: таблица signed claims и их поставщиков/верификаторов, точные immutable pins, список GitHub workflow YAML и broker SQL changes, dual-pin принятие и rollback, synthetic test report с логами без PHI, TEST readback, независимый security GO/NO-GO. Поскольку текущий мост тестового owner OAuth ещё имеет самостоятельные NO-GO, эти работы координируются, а не считаются уже завершёнными.

**Никакая часть предложения не отменяет действующий приватный HealthDB State/Manual, single-writer, accepted Writer main SHA или OWNER clinical instruction.**
