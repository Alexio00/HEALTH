# HEALTH — независимые циклы разработки и приёмки (предложение 14.10.2026)

> **Статус: Draft, не активная release-политика.** Существующие приватные Project State/Manual и фактические runtime/CI-проверки имеют приоритет. Этот документ сам по себе не разрешает переключать Writer, запускать backup, добавлять medical SQL или сливать PR.

## Почему это нужно

Принятый production Writer привязан к точному **HEALTH/main** SHA `3409791f1ffc5749020e7ff07139b0cec722f6fc`. Основной workflow `.github/workflows/writer-authorization.yml` сейчас дополнительно требует `github.ref == refs/heads/main`, `github.actor_id == 308028794` и `vars.HEALTH_WRITER_ACCEPTED_SHA == github.sha`. Поэтому произвольный merge в `main`, даже документации или launcher, изменяет доказательство авторизации и требует согласованного Writer reacceptance. **Не удалять эти условия до принятия новой схемы доверия.**

Проверено на дату предложения: `pwa` находится на 70 коммитов впереди `main` без его изменения, а `scheduler-code` пока равна `main`; большая часть Scheduler — лишь Draft PR #73 в `scheduler-code`, trust launchers — лишь Draft PR #72 в `main`. Публикация Pages происходит из `pwa`; защита scope сохраняет открытый HIGH Issue #50. Никакие релизы не разрешены автоматически.

## Целевые границы, без дополнительных сервисов и репозиториев

| Контур | Где разрабатывается | Где выпускается | Что блокирует |
|---|---|---|---|
| **Writer** | новая `writer-code` на точном принятом main SHA (создана как staging; ещё не защищена) и feature PR в эту ветку | только **immutable accepted code SHA** после отдельного независимого принятия, обновления broker/runtime и реальных отрицательных проверок | клинические миграции, Writer RPC, Verifier, Validation, signing, owner identity и authorizer |
| **PWA** | feature branches **от текущей `pwa`** | PR → protected `pwa` → Pages + постпроверка | независимые чтения и отображение при совместимом контракте; не имеет права записывать данные |
| **Scheduler code** | feature branches → PR #73 / будущие PR в `scheduler-code` | исполняемый код по **точному принятому SHA**, принятый отдельно от Writer | отдельное принятие кода, RLS/Secrets/Restore; ничего не запускается из candidate PR |
| **Scheduler launcher** | только утверждённые workflows в default `main`, сейчас Draft #72 | bootstrap в **окно согласованного принятия Writer/main**; далее изменение принятого executable SHA без нового checkout moving branch | GitHub schedule/workflow_dispatch требует файл в default branch; доверие caller/issuer и IAM нельзя делегировать кандидату |
| **Schema / Read API** | feature + контроль Issue #62 | совместимые читательские изменения могут выпускаться отдельно после RLS/reader acceptance; любые изменения записываемой схемы — **Writer-impact** | explicit allowlist, exact INSERT columns, checkpoint, Validation, Source и независимый verifier |

**Важно:** ветки не являются режимом безопасности. Разграничение основано на GitHub Rulesets/статусах, exact SHA, trust issuer, раздельных секретах/ролях, независимой проверке и фактическом runtime readback.

## Пять постоянных веток и место архитектуры

Ровно пять самостоятельных долгоживущих веток, перечисленных по функциям:

| Git-ветка | Назначение | Условия |
|---|---|---|
| `main` | доверенный default control plane, текущий production Writer pin, минимальные launchers | только согласованные изменения и пока что принятая процедура переутверждения Writer SHA |
| `writer-code` | разработка и синтетическая проверка bounded Writer / Verifier / Validation | staging от принятого main SHA; никакой автоматической медицинской авторизации из этой ветки |
| `pwa` | read-only интерфейс, Pages и frontend release | защищённый PR, проверка области изменения, отдельный browser postcheck |
| `scheduler-code` | исполняемые scripts Scheduler, восстановление, keepalive, тесты | Draft #73, выпуск только по принятому immutable SHA |
| `scheduler` | **только heartbeat-коммиты**, не код и не запускатель | никогда не сливать обратно в main/pwa/writer-code/scheduler-code; cron workflow размещается в default main |

**Ветка `scheduler` НЕ обязана иметь Git ancestry от `scheduler-code`.** В существующей реализации она исторически ответвлена от `main`; её связь с кодом Scheduler — операционная, через доверенный launcher, а не через merge. Нельзя выполнять rebasing `scheduler` на `scheduler-code` или «синхронизацию кода» с этой веткой.

**Постоянную ветку `architecture` не создавать.** Общесистемная архитектура — временная `maintenance/*` / `docs/*` ветка с Draft PR в `main`. Компонентные детали живут рядом с конкретным компонентом: PWA-политика в `pwa`, Scheduler design в `scheduler-code`, Writer design в `writer-code`. Общая документация после согласования принимается только в предусмотренное main-окно, с соблюдением фактического Writer SHA gate.

### Подтверждённые GitHub Rulesets (readback 14.10.2026)

Прямое чтение `GET /repos/Alexio00/HEALTH/branches/{branch}` и `GET /repos/Alexio00/HEALTH/rulesets/{id}` через GitHub:

| Ветка | `protected` | Активный Ruleset | Required check | Вывод |
|---|---:|---|---|---|
| `main` | true | 25010398 — Protect Writer main | **нет** | PR, no delete/force push, без bypass |
| `pwa` | true | 25010980 — Protect PWA | `static` (integration ID 15368) | Scope spoof HIGH #50 **открыт** |
| `scheduler-code` | true | 25029979 — Protect Scheduler Code | **нет** | PR и no delete/force push есть, независимого mandatory check нет |
| `writer-code` | **false** | **отсутствует** | **нет** | **НЕ сливать PR в эту ветку до отдельного принятия защиты** |

Все три существующие правила `enforcement=active`, `bypass_actors=[]`, требуют PR и запрещают удаление и non-fast-forward. `protected=true` не доказывает защиту required check от имитации другим workflow. Эту таблицу надо снова перечитать непосредственно перед включением новых rules/merge.

**Следующее конкретное действие владельца в GitHub Settings → Rules → Rulesets:** создать активную веточно-адресную защиту `writer-code` (PR required, block force-push/deletion, без bypass). Для `scheduler-code` не включать непроверенную обязательную проверку до успешного независимого trusted issuer и отрицательных PR тестов. До выполнения соответствующих проверок держать оба PR #35 и #73 в Draft, не запускать release. Административное редактирование GitHub Rulesets недоступно текущему коннектору, поэтому изменения настроек этим документом **не сделаны**.

### Контроль защиты и необходимое действие владельца

GitHub-ветка **не защищается самим созданием**. Для `writer-code` и `scheduler-code` нужно через GitHub Settings → Rules → Rulesets независимо подтвердить:

1. Ограничение на каждую конкретную ветку; PR перед merge, запрет удаления и force-push, без необоснованных bypass; правила действительно Active.
2. Required check существует и получает результат от принятого trusted issuer, не от PR-кандидата с тем же именем. Держать текущие required checks до проверенного перехода.
3. Для `writer-code` запрет изменений trusted authorizer/workflow из самой ветки. Для `scheduler-code` запрет schedule/backup launchers и секретов.
4. Реальные положительные/отрицательные PR-проверки на актуальном SHA, проверка Rule enforcement и конечного Github Pages/Writer/Scheduler результата.
5. **Никаких self-controlled tests как единственного proof**. Защита требует независимого code review и Issue #50/H-01 closed по факту adversarial проверки.

Интеграция GitHub в текущем чате не предоставляет управления Rulesets. Пока эти настройки и их enforcement не подтверждены, оба направления можно разрабатывать через Draft PR, **но не использовать их коммиты как production release**.

## Немедленно применимая маршрутизация

1. **PWA_ONLY**: UI/assets/render/read-only запросы на существующей принятой схеме и в пределах `frontend/**`; PR в `pwa`. Сохранить `static` и постпроверку. Workflow/auth/service-worker/release инструменты требуют дополнительного review; не полагаться только на self-controlled CI (#50).
2. **READ_SCHEMA_ONLY**: отдельный SQL-кандидат; доказать, что изменения добавочны, read-only, не меняют writable columns, triggers/check constraints, roles/entitlements Writer. Отдельная DB/schema maintenance только с точным owner approval; не выдавать READ_SCHEMA_ONLY по имени файла.
3. **WRITER_IMPACT**: таблица/атрибут/тип/FK/status/trigger/constraint и любые semantic/Source изменения, которые Writer должен публиковать/валидировать. Держать отдельным Draft до единого end-to-end принятия Schema + Writer + Verifier + Validation + PWA. Вакцинация #41/#45/#51/#59 — текущий пример.
4. **SCHEDULER_CODE_ONLY**: `scripts/scheduler/**`, ограниченные `scripts/automation/**`, тесты и документация, без production workflows и секретов. Ветка и PR в `scheduler-code`. #70/#71/#67/#64 — исторические конкурентные кандидаты; не сливать их поверх консолидированного #73.
5. **DEFAULT_BRANCH_LAUNCHER / TRUST**: `.github/workflows/**` с schedule, writer OIDC, trusted scope/Pages и Secrets; нельзя замаскировать как обычный UI/Scheduler change. PR только в `main` в отдельно принятом release window; Issue #50/#65.
6. **DOCS**: development docs не требуют production. Документы Writer/main могут долго существовать в Draft: merge в `main` меняет accepted SHA. Актуальные приватные управляющие Project State/Manual обновляются отдельной контролируемой операцией, не неявно из GitHub.

## Реальное разделение Writer code release и main HEAD — отдельный security gate

**Нельзя** просто заменить `github.sha == vars.HEALTH_WRITER_ACCEPTED_SHA` условием `job_workflow_sha == accepted_sha` или убрать `github.ref`. Защищённая base `main` и доверенный issuer, owner click, подписанная проверка GitHub и независимое одобрение обязаны быть сохранены. Возможная реализация:

1. `writer-code` — только разработка; защищённый PR, запрет force-push и секретов. Release принимает **полный immutable commit SHA**, не moving branch/tag.
2. Предусмотреть минимальный trusted GitHub Actions launcher в default `main` с непереписываемой базовой политикой и отдельной независимой проверкой PR scope (HIGH #50). GitHub требует workflow file в default branch для `workflow_dispatch` и `schedule`. Недоверенный candidate не может изменить launcher, checkout ref или required check.
3. Выполнять только принятый immutable Writer source **проверенный SHA** (например, защищённый reusable workflow, pinned by SHA), но не считать само его использование доказательством. GitHub OIDC claims `actor_id`, `repository_id`, `ref`, `workflow_ref`, `workflow_sha`, `job_workflow_ref/job_workflow_sha` требуют независимой broker-проверки. Только pinned reusable-workflow claim без trust boundary на caller **не достаточен**.
4. Отдельно в reviewer-модели проверить protected main workflow, owner GitHub signed authorization, криптографическую привязку `request_key/kind/digest/candidate_sha`, accepted code SHA, однократное согласие и подпись незалежимого verifier. Не пытаться менять обычный accepted Writer пока новый путь не прошёл TEST negative E2E.
5. Пробная схема в HEALTH-TEST (не production), independent adversarial audit, backup/recovery, owner approval, после чего **одно** контролируемое переключение trust и main accepted SHA. Только после этого unrelated `main` docs/launcher merges перестанут блокировать клинический Writer.

### Невыпущенная архитектура / сдерживающие обстоятельства

- Остаются открытыми HIGH [#50](https://github.com/Alexio00/HEALTH/issues/50), schema compatibility [#62](https://github.com/Alexio00/HEALTH/issues/62), consolidation [#65](https://github.com/Alexio00/HEALTH/issues/65), [#69](https://github.com/Alexio00/HEALTH/issues/69).
- Готовность полного резервирования проверяется настоящим restore и двумя последующими циклами, прежде чем выключать старый SHEDULLER. Никогда не выполнять два независимых backup-ротатора одновременно.
- Не создавать альтернативный writer, не менять `writer_model=single-writer`, не подменять bounded Writer административным SQL/Secrets.
- Нельзя удалять старые ветки, PR или private SHEDULLER до сохранения evidence и отдельного owner cleanup решения.
- На первом этапе **нет** role/grant/broker/run/deploy/policy modifications; branch existence не означает защиту GitHub Rulesets.

## Проверяемые критерии завершения

- **PWA**: отдельный PR только PWA, independent scope check (#50) закрыт фактическими negative PR тестами, release SHA и browser postcheck, unchanged Writer accepted SHA.
- **Scheduler code**: #73 проверен/принят в `scheduler-code`, trusted scope и независимые restore/backup acceptance; runtime не включает moving branch. Bootstrap #72 только в принятом main window.
- **Writer**: pinned writer release работоспособен при обновлении unrelated main commit (NEGATIVE: поддельный launcher/токен/неподтверждённый код не авторизуются). Broker, Actions и runtime согласованы, обязательно отдельное принятие и recovery GO.
- **Schema**: матрица Issue #62 применена на каждый PR, реальный функциональный пример end-to-end validated.

**Источники:** действующие приватные HealthDB State/Manual; [GitHub OIDC reference](https://docs.github.com/en/actions/reference/security/oidc); [GitHub workflow_dispatch semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows); живые PR #39/#50/#51/#59/#62/#65/#69/#72/#73. Ни один пункт документа не утверждает, что это уже production.
