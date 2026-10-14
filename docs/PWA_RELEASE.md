# HEALTH PWA — эксплуатация, выпуск и откат

Это **действующее руководство PWA**. Обязательная маршрутизация веток, разделение пересекающихся PR и ограничения Writer описаны также в [AGENTS.md](../AGENTS.md). Перед новой задачей проверяйте живые ветки и открытые PR; приведённые ниже исторические снимки не являются разрешением на merge.

**Production Writer:** принят только из `HEALTH/main`, с точной подписанной авторизацией владельца, принятым SHA в переменной GitHub Actions, политикой Supabase Edge broker и `health_writer.runtime_policy.code_sha`. Ни одна инструкция PWA не ослабляет этих требований.

**Публикация frontend:** `HEALTH/pwa` — самостоятельный источник `Deploy HEALTH PWA`. Frontend PR направляются в `pwa`, **не** в `main`. Merge в `pwa` не изменяет принятый Writer SHA. Запрещено запускать workflow клинической авторизации из `pwa`.

## Компоненты и ограничения

- **GitHub Pages** раздаёт **публичные** статические файлы. Доступ к странице не означает доступ к медицинским данным. GitHub Pages нельзя рассматривать как приватное хранилище или backend.
- **Supabase Auth + RLS** обеспечивают доступ к данным: браузер выполняет только аутентифицированные `GET`/`SELECT` в PostgREST. Само наличие публичного `SUPABASE_PUBLISHABLE_KEY` не предоставляет привилегий. Service-role key, секреты, реальные Sources и медицинские строки не помещаются в репозиторий или Pages.
- **PWA** кэширует только проверенную публичную оболочку, а не ответы Supabase; наличие offline-страницы не означает работу медицинской карты без сети.
- **Writer** — отдельный ограниченный и независимо проверяемый контур клинической записи. GitHub merge, статический сайт, зелёный CI или успешный вход в Auth не предоставляют ему прав.
- **Scheduler** не запускается через PWA. Отдельные `scheduler-code`/`scheduler` и main launchers имеют собственную приёмку; PWA PR не должен запускать backup, GitHub dispatch или выдавать clinical credentials.

Актуальное руководство интерфейса: [frontend/README.md](../frontend/README.md).

## Процедура выпуска PWA

1. Создайте отдельную ветку от **текущего `pwa` HEAD**. Меняйте только допустимые UI/assets либо PWA-документацию. Проверьте отсутствие изменений Writer scripts, SQL schemas, Edge broker и authorization workflows. Для изменения release controls действует более строгий порядок ниже.
2. Зафиксируйте полные 40-символьные `BASE_SHA` и `HEAD_SHA`, целевую `pwa` и **полный diff**. Добейтесь успешного `HEALTH code validation` для PR; обязательный job — `static`. Независимое review точного SHA и отдельный явный `OWNER_GO` обязательны **до merge**. Непосредственно перед merge заново проверьте HEAD/BASE, diff, обсуждения, текущий Ruleset и CI. Изменение SHA аннулирует предыдущее принятие.
3. После **разрешённого merge**, если push затронул `frontend/**` или `.github/workflows/deploy-pages.yml`, из `pwa` автоматически стартует `Deploy HEALTH PWA`. Workflow использует concurrency group `pages-pwa` (отдельную от legacy group `pages` в `main`). Job **Verify PWA before release** проверяет синтаксис frontend, синтетические контракты и public secret-pattern guard, собирает и загружает точно проверенный Pages artifact. Job **Publish verified PWA** зависит от первого job и допускает deploy только из `refs/heads/pwa`. Это обязательный pre-deploy gate, **не** замена полного `HEALTH code validation` на PR.
4. Проверьте job **Verify published release bytes** (`postcheck`), точный SHA релиза, `release.json`, все хеши ресурсов, затем поведение в браузере под **разрешённой** сессией. Успех Pages deploy сам по себе не является UI smoke-test или проверкой Writer. Для чисто документационного merge (только `frontend/README.md` и `docs/PWA_RELEASE.md`) `push` запускает `HEALTH code validation` по `docs/**`/`frontend/**`, но триггер Pages имеет собственные фильтры: изменение `frontend/README.md` находится под `frontend/**` и **поэтому тоже может инициировать Pages workflow**, даже если опубликованные runtime-файлы не меняются. Не считайте docs-only PR гарантией отсутствия Pages run после merge.
5. Проверьте, что SHA `main` и принятый Supabase Writer SHA не изменились. Нельзя обходить accepted-code boundary Writer прямым SQL.

При неудаче deploy можно повторить **только** deploy job, пока в run остаётся единственный действительный artifact, либо начать новый `pwa` workflow run. Не перезапускайте загрузивший artifact job или весь workflow с тем же run ID: повторный `github-pages` artifact может сломать `actions/deploy-pages`. При сомнении безопаснее новый run.

Legacy Pages workflow остаётся в `main`, но environment `github-pages` ограничен владельцем веткой `pwa`; не ослабляйте ограничение. Удаление legacy workflow предусмотрено отдельно принимаемым Writer-изменением PR [#39](https://github.com/Alexio00/HEALTH/pull/39). Если это изменение когда-либо будет принято, нужен **новый** `workflow_dispatch` деплой из `pwa` для восстановления точно одобренной редакции. Нельзя переносить frontend-файлы Writer PR в `main` исходя из предположения, что Pages останется неизменным.

## Защищённая ветка `pwa` — проверенная настройка GitHub

На момент проверки 14.10.2026 GitHub branch API возвращает `protected: true`. Ruleset [Protect PWA, ID 25010980](https://github.com/Alexio00/HEALTH/rules/25010980) имеет `enforcement: active`, адресован **только** `refs/heads/pwa` и требует:

- merge через PR (`pull_request`), без обязательного отдельного человеческого approval при единственном владельце;
- обязательный Actions status `static` из `HEALTH code validation`, `strict_required_status_checks_policy: true` — обновлённая база;
- запрет удаления и non-fast-forward/force-push;
- отсутствие разрешённых bypass actors (`bypass_actors: []`).

GitHub Free поддерживает Rulesets в **публичном** репозитории; платный тариф для этого не требуется. Проверять настройку следует в GitHub **Settings → Rules → Rulesets**. Не расширяйте Ruleset на `main` или ветки Writer. Не делайте pre-merge обязательным job публикации `github-pages`: он запускается после merge, и такое правило заблокирует PR. Если появится независимый reviewer, требования к согласованию можно отдельно пересмотреть.

Workflow `HEALTH code validation` запускается для **каждого** `pull_request`, направленного в `pwa`, даже при изменении только workflows/инструкций, поэтому `static` должен появляться в PR. `push`-триггер CI имеет фильтры путей, что не равно PR-триггеру. Чистый CI и реально опубликованный `pwa` — разные проверки.

Ограничение `github-pages` environment на `pwa` было установлено владельцем; сам `deploy-pages.yml` дополнительно отказывает refs, отличным от `pwa`. Перед реальным релизом перепроверяйте environment в настройках GitHub: строка в документации сама по себе не обеспечивает эту защиту.

## Правила scope и доверенная проверка PR

Обычный PWA PR может менять обычные файлы внутри `frontend/`, а за его пределами — только `AGENTS.md` либо `docs/PWA_RELEASE.md`. Backend, SQL, приватные пути и symlinks запрещены. Права и разрешённость каждого кандидата проверяет `frontend/release/scope.mjs`, запущенный из объектов **защищённой base**, а не из проверяемой ветки.

К изменениям release controls относятся `frontend/release/` и перечисленные PWA workflow-файлы. Такой PR должен быть создан владельцем с GitHub user ID `308028794` и иметь **отдельную точную строку** в теле PR:

```text
PWA-RELEASE-CONTROL: <40-character head SHA>
```

Изменение HEAD требует новой строки и нового review. **Не** добавляйте её к неизвестному PR только ради PASS. Изменения `.github/workflows/code-validation.yml` вне ограниченного frontend-check блока запрещены даже при авторизации release-control: Writer/OIDC-части должны оставаться побайтово прежними.

Ранее предложенный отдельный `pull_request_target` workflow не запускался: GitHub загружает его из default branch `main`. Его убрали из `pwa`, и считать его действующей защитой нельзя. Рабочий `static` использует base-sourced scope и проверяет Git objects кандидата.

**Ограничение безопасности (HIGH [#50](https://github.com/Alexio00/HEALTH/issues/50) — OPEN):** текущий Ruleset привязан к имени `static` и GitHub Actions, **не** к неизменяемой идентичности конкретного workflow. Вредоносный PR может попытаться объявить другой Actions job с таким же названием. Нет независимого технически enforced `pwa` scope-check; текущая защита — defense-in-depth и обязательная процедура ручной независимой приёмки. Не объявляйте её неуязвимым барьером для hostile contributor. Для строгой защиты потребуется отдельный проверенный issuer/status либо подходящее правило GitHub. Не ослабляйте текущий Ruleset и не добавляйте несуществующий required check: это заблокирует PR. Начальная scope-политика проверялась относительно baseline `93964e3524171d789f03608958a6b0740bae23ee`.

## Точная сборка Pages artifact

Сборка разрешена только при `GITHUB_REF=refs/heads/pwa` и совпадении `GITHUB_SHA` с checkout `git HEAD`. Скрипт `frontend/release/build.mjs` копирует **15 перечисленных** runtime-файлов во временную директорию runner, вставляет SHA в `index.html` и `sw.js`, генерирует `release.json` (schema 1, точный SHA, SHA-256 всех runtime-файлов). Исходные README, тесты и release tooling не публикуются как часть artifact.

Индикатор версии в footer показывает короткий SHA **этого HTML artifact**, а не якобы уже вышедшего более нового релиза.

Service worker использует кэш `health-shell-<full SHA>`. Установка получает восемь разрешённых ресурсов с `redirect: "error"` и проверяет MIME, cache policy и SHA-256 байтов **до** помещения их в кэш и `skipWaiting`. Каждая активная версия обслуживает согласованный набор статических ресурсов. При активации удаляются старые `health-shell-*` кэши, но не посторонние. `clients.claim` и однократная перезагрузка по `controllerchange` переводят управляемую страницу на новую версию. `updateViaCache: "none"` исключает зависимость обновления worker от HTTP cache браузера. При устаревшем CDN-файле новая установка отвергается, прежний worker продолжает работу. Hash-маршруты используют тот же `index.html`.

В offline-кэш **не** попадают query URL, OAuth test pages, API, произвольные пути, Authorization/Range requests, redirects, ответы с не-200, неверным MIME, `private`/`no-store`/`no-cache`. Supabase responses не сохраняются в CacheStorage; тестовое OAuth-согласие требует сети.

## Постпроверка опубликованных файлов

Job `Verify published release bytes` запускается **после** `Publish verified PWA` в том же workflow. Скрипт `frontend/release/smoke.mjs` обращается к опубликованному корню, `release.json` и всем 15 файлам с `cache: "no-store"`; сверяет HTTP status, MIME, точный SHA и SHA-256 полных байтов.

Повторные попытки ограничены **12** (по **10 секунд** между попытками); timeout одного запроса — **10 секунд**, timeout job — **5 минут**. `continue-on-error` нет. Если postcheck FAIL, весь release workflow FAIL, даже когда `Publish verified PWA` уже выполнился. Это обнаружение несовпадений, **не атомарный rollback**: неверная версия может уже быть доступна на Pages. Источник сигналов — статус GitHub Actions и уведомления, без платного сервиса.

Совпавший прежний marker без побайтового совпадения файлов — FAIL. HTTP PASS не доказывает корректность интерфейса в авторизованной сессии и поведение установленного PWA на устройстве.

## Откат через защищённый PR

1. Выберите ранее проверенный `pwa` commit и его release/evidence.
2. Получите текущий `pwa`, создайте **новую** rollback-ветку от него. Никакого reset удалённого ref, force-push или обхода Ruleset.
3. Отмените только ошибочное frontend-изменение, разрешая конфликты с действующими маршрутизацией, OAuth assets и правилами релиза. Для merge-коммита пример: `git revert -m 1 <SHA>`. Если такой revert удалит безопасный worker/build pipeline, восстановите только затронутые UI-файлы из known-good tree. Пересоберите с **текущими** инструментами; не копируйте старые `release.json` или сгенерированный worker.
4. Сверьте полный diff, откройте PR в `pwa`. Для release-control изменения нужен PR владельца с точной строкой `PWA-RELEASE-CONTROL: <40-character head SHA>`. Дождитесь текущего обязательного `static` с base-sourced scope, независимой проверки и отдельного `OWNER_GO`. Без bypass.
5. Выполните обычный разрешённый merge. Его SHA — **новая** идентичность релиза и кэша.
6. Проверьте Verify/Publish/postcheck, фактический marker SHA и все байты. Сначала просмотрите публичную оболочку без входа; клинические страницы проверяйте только в отдельно разрешённой сессии. Сохраните результаты синтетических offline-тестов.
7. Неудачная установка оставляет прежний worker. Успешная установка исправленной версии переключает кэш и перезагружает контролируемые страницы. При необходимости закройте/повторно откройте PWA для проверки обновления. **Не** очищайте без разбора медицинское браузерное хранилище.
8. Если postcheck либо rollback неудачен, сохраните evidence, остановите несвязанные релизы, найдите ошибку CDN/asset/build и подготовьте отдельный repair PR от актуального `pwa`. При необходимости повторяйте только deploy/postcheck, но не создавайте дубликат `github-pages` artifact под тем же run ID.

Синтетический регрессионный набор собирает два релиза с разными SHA, проверяет смену идентичности worker/index, имитирует устаревшие файлы и неудачную установку без частичной активации кэша, ограниченные retry и восстановление целой оболочки. Он не выполняет production rollback.

Независимый `pull_request_target`-механизм потребовал бы отдельно принятого изменения default branch/Writer SHA либо внешнего issuer. Эта документация не внедряет такой механизм. [GitHub: securely using pull_request_target](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target).

## Совместимость с текущим экраном вакцинации

В `pwa` уже приняты интерфейсные изменения PR [#80](https://github.com/Alexio00/HEALTH/pull/80) и [#85](https://github.com/Alexio00/HEALTH/pull/85). В истории вакцинаций поддержано раскрытие нескольких **уже присутствующих** инфекций в тегах: это лишь визуальное представление и **не** доказательство одного комбинированного введения или числа антигенных доз. Текущие read-only представления основаны на `records.body_text` и `records.summary`, а также `plan_items`: распознанные фрагменты раздела вакцинации из `body_text` имеют приоритет; при их отсутствии используется `summary`. Это эвристика отображения, **не** канонический реестр введённых доз; новая схема и клиническая запись не создаются. Консультации/антитела/отменённые REC не должны превращаться в подтверждённые введения, а неизвестные связи не угадываются.

PWA-only UI можно развивать по существующему read-only контракту независимо от новой модели Writer, но изменения OAuth/consent, Supabase-client, service worker, release tooling и Actions требуют отдельного security/threat review. HIGH Issue [#50](https://github.com/Alexio00/HEALTH/issues/50) остаётся OPEN. Новые медицинские сущности, writable schema и статусы вакцинации — `WRITER_IMPACT` (Issue [#62](https://github.com/Alexio00/HEALTH/issues/62)): не выпускать их без принятых bounded Writer, Verifier, Validation и независимого readback. PR [#51](https://github.com/Alexio00/HEALTH/pull/51) и [#59](https://github.com/Alexio00/HEALTH/pull/59) требуют отделять безопасный визуальный объём от новых медицинских зависимостей.

Staging `writer-code` предназначена для будущей разработки Writer и **не** является production ref. До отдельной security/operational acceptance Writer связан с exact `main` SHA. `scheduler-code` — разработка Scheduler, `scheduler` — отдельный служебный heartbeat, main launchers требуют принятия. PWA CI/release не должны запускать Writer authorizer, backup, GitHub dispatch или получать clinical credentials. Подробнее — [Draft PR #76](https://github.com/Alexio00/HEALTH/pull/76); проектные документы из Draft PR не являются действующим runtime.

## Другие ветки и PR: исторический снимок, не действующее распоряжение

Снимок координации от **13.10.2026**: перед новой работой **обязательно** перечитайте актуальные PR и ветки. Этот список не даёт права merge, переписывания или удаления.

- PR #38 (Vaccination) был объединён в `pwa` 13.10.2026. Сохраняйте модуль вакцинации и автоматический SHA-bound shell cache, как и остальные ранее принятые изменения.
- PR [#36](https://github.com/Alexio00/HEALTH/pull/36), `feature/supabase-test-consent-ui-20261013`: четыре файла `frontend/oauth-test/*` уже есть в `pwa` благодаря прежнему Pages deploy. Нельзя переносить их в `main` только ради публикации; новые consent/auth flows требуют отдельной threat model.
- PR [#35](https://github.com/Alexio00/HEALTH/pull/35), `feature/chat-writer-contract-20261013`: Writer/backend и `code-validation.yml` относятся к принятию `main` по точному SHA. При синхронизации не удаляйте `pwa` CI-триггеры.
- PR [#33](https://github.com/Alexio00/HEALTH/pull/33), `maintenance/ru-governance-legacy-independence-20261013`: затрагивает Writer, governance и `frontend/README.md`. Разделите или явно согласуйте scope, чтобы не перезаписать актуальные PWA-инструкции устаревшим README.
- PR [#27](https://github.com/Alexio00/HEALTH/pull/27), `migration/planned-medication-status`: SQL migration и старые инструменты требуют новой проверки применимости к каноническому Supabase и безопасности. Старый migration-код не является автоматическим production fix.
- PR [#22](https://github.com/Alexio00/HEALTH/pull/22), `test/nonmutating-probe-handoff`: docs-only в `main` всё равно меняет принятый SHA Writer; нужна отдельная авторизация либо отложенное принятие.

Исторические/осиротевшие ветки: `maintenance/pwa-ui-refine-20261007`, `maintenance/frontend-accordion-medrec-visits-20261013`, `release/pages-ui-20261013-preserve-oauth-test`. Новая работа начинается от **живого** `pwa` или `main`, не от старой release-ветки. Удаление — только по отдельному решению владельца.

## Две независимые процедуры принятия

**PWA:** полный BASE/HEAD SHA + точный diff → независимая проверка совместимости, безопасности, негативных тестов и отката → отдельный GO владельца на **этот** SHA → немедленная перепроверка HEAD/BASE, Ruleset, незавершённых обсуждений и `static` → разрешённый merge → фактический Pages release SHA, Verify/Publish/postcheck и браузерный smoke-test в авторизованной сессии (либо явное `NOT_VERIFIED`). CI PASS не равен независимому review или GO.

**Writer:** отдельная независимая рецензия кода, повторное принятие **точного `main` SHA** в GitHub owner policy, Edge broker и runtime, проверка ограниченной роли. Merge в `pwa` не разрешает медицинскую операцию. Нельзя заменять отсутствующий приватный Writer operator административным Supabase SQL.

## Дальнейшее развитие и ссылки

- `pwa` сохраняет уже опубликованные `frontend/oauth-test/*`; UI merge не должен удалять их.
- Параллельный Writer остаётся в отдельных ветках, `main` — текущий ref подписанной авторизации. Полная долговременная изоляция потребует отдельно принятого immutable Writer ref/repository и удаления пути frontend auto-deploy из `main`, с новым независимым аудитом, координированным повторным принятием и разрешением владельца. Обычный `pwa` UI PR этой миграции не требует.
- Руководство описывает **текущую** эксплуатацию; английские исторические отчёты аудитов, прошлые migrations и решения не переписываются. Draft PR [#92](https://github.com/Alexio00/HEALTH/pull/92) — отдельная документационная работа; данный документ не меняет её scope.
- [GitHub Pages: configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site); [GitHub: about rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).

**Проверка публичной приватности:** `scripts/validation/public_secret_guard.py` исключает файлы с расширением `.md`. Поэтому на каждый docs-only PR нужны отдельный просмотр полного Markdown-diff, проверка всех новых ссылок, ручная/дополнительная проверка медицинских строк, приватных IDs, credentials, токенов и секретов. Зелёный public secret-pattern guard **не подтверждает** чистоту Markdown.
