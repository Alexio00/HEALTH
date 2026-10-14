# HEALTH PWA — эксплуатация, выпуск и откат

Актуальная процедура для read-only frontend в `Alexio00/HEALTH`. Обязательная маршрутизация изменений и разрешение межветочных конфликтов — в [`AGENTS.md`](../AGENTS.md). Перед каждой задачей проверяй живые `main`, `pwa`, открытые PR и CI; старый перечень веток не даёт права на merge, rewrite или удаление.

**Границы:** production Writer принимается отдельно от `HEALTH/main` по точному SHA с подписанной авторизацией владельца, GitHub Actions variable, Supabase Edge broker policy и `health_writer.runtime_policy.code_sha`. Frontend публикуется только из `HEALTH/pwa` посредством `Deploy HEALTH PWA`. Merge в `pwa` не меняет принятый Writer SHA, не активирует медицинскую операцию и не разрешает clinical authorization workflow. Writer/SQL/Edge/OIDC/backup и медицинские данные не входят в PWA PR.

## 1. Что именно публикуется

GitHub Pages — публичный статический хостинг: любой посетитель может скачать HTML, JS, CSS, service worker и `release.json`. **Публичность кода не означает публичность базы.** Медицинские сведения читаются только после Supabase Auth и согласно RLS; анонимные SELECT к медицинским таблицам запрещены. Клиент делает read-only GET/SELECT, хранит действующую Auth-сессию в `localStorage`, не сохраняет медицинские ответы offline. Только публичный publishable/anon key допустим в браузерном коде; `service_role`, Writer secrets, токены, полные REC, файлы Sources и закрытые Google Drive locator ID недопустимы в репозитории и Pages artifact.

Страница «Вакцинация» отображает **производную read-only проекцию** из `records` и `plan_items` с фиксированным `metadata.kind=вакцинация`. Сведения о проведённых дозах требуют подтверждённой REC; консультации/анализы антител/отменённые REC не являются доказательством введения. Раскрытие нескольких инфекций в истории — только интерфейс, не доказательство одной инъекции или этапа каждого антигена. Ни PWA, ни её выпуск не создают канонический реестр доз и не проводят клиническую сверку; новую writable схему/связи/статусы выпускать только по отдельно принятому [Issue #62](https://github.com/Alexio00/HEALTH/issues/62) контракту Writer/Verifier/Validation.

## 2. Ветки, защита и release gate

- `pwa` — действующий источник GitHub Pages. Рабочую ветку создавать от **актуального** `pwa`; PR направлять в `pwa`, не в `main`. Сохранять ранее выпущенные UI-функции, файлы `frontend/oauth-test/*`, маршруты, вакцинацию и SHA-bound offline-shell. PR, сделанный от `main`, нельзя просто retarget без сверки исходников, тестов и конфликтов.
- `main` — принятый Writer/серверная реализация. Даже docs-only merge в `main` меняет code SHA и требует отдельного принятия; текущий PWA-only PR туда не направлять.
- `writer-code` — staging разработки Writer, не production. `scheduler-code` — отдельная разработка Scheduler; `scheduler` — контур служебной активности. Ни Scheduler, ни backup/Secrets, ни Writer authorizer не запускаются через PWA CI/Pages.
- Действующий репозиторный Ruleset [`Protect PWA`](https://github.com/Alexio00/HEALTH/rules/25010980), ID `25010980`, применяется **только** к `refs/heads/pwa` и имеет `Active`. Проверенное состояние на 14.10.2026: `protected: true`, PR обязателен; блокируются delete и non-fast-forward/force-push; требуется актуальность ветки (`strict_required_status_checks_policy=true`) и GitHub Actions status `static` (integration ID `15368`); `bypass_actors=[]`. Число обязательных review approvals — `0`, не требовать собственного формального approval единственного владельца. Для следующего выпуска проверить Ruleset заново, а не полагаться на эту дату.
- Важное ограничение [HIGH #50](https://github.com/Alexio00/HEALTH/issues/50): Ruleset привязывает имя `static` к GitHub Actions, а **не к неизменяемой доверенной идентичности workflow**. Злоумышленный PR потенциально может выдать другой Actions job с этим именем. Контроль состава изменений из защищённой базы — defense in depth, но не непреодолимая гарантия. Ручная независимая приёмка exact SHA и отдельный `OWNER_GO` обязательны. Не ослаблять Ruleset, не подключать несуществующий required check и не считать HIGH закрытым.
- Существующий `github-pages` environment, согласно принятой эксплуатационной настройке, ограничен веткой `pwa`: старый Pages workflow в `main` не должен публиковать сайт. Workflow `pwa` дополнительно проверяет `github.ref == 'refs/heads/pwa'`. Ограничение environment — настройка GitHub, не следствие текста Markdown: её нужно сохранять и перепроверять в GitHub Settings. Удаление старого workflow из `main` — отдельная Writer-регламентная операция, не часть этого PR.

Для нового PWA-кандидата обязательна последовательность из действующего Project Manual: (1) заморозить **полные** 40-символьные `BASE_SHA`/`HEAD_SHA`, назначение и полный diff; (2) получить независимую от автора проверку совместимости, безопасности, негативных тестов и rollback с вердиктом **на данный exact SHA**; (3) получить отдельный явный `OWNER_GO` на него; (4) непосредственно перед merge повторить проверки HEAD, BASE, diff, Ruleset, нерешённых обсуждений и требуемого `static`; любое изменение кандидата обнуляет предыдущую приёмку; (5) после разрешённого merge проверить точный release SHA, Pages/postcheck и UI под разрешённой сессией. **CI PASS ≠ независимая приёмка ≠ OWNER_GO ≠ подтверждённая эксплуатация.** Auto-merge не применять.

## 3. CI и политика состава PWA PR

`HEALTH code validation` — `.github/workflows/code-validation.yml` — запускается на каждом `pull_request` к `pwa` (в том числе docs-only, root- и workflow-only). Для `push` в `pwa` действует фильтрация `paths`; наличие статуса PR `static` и успешность отдельного push run — разные проверки. Required check — **job `static`** из `HEALTH code validation`, не deployment `github-pages`: последний выполняется *после* merge, требование его до merge создало бы deadlock.

Для PWA PR `static` исполняет `frontend/release/scope.mjs` из Git-объекта **base SHA** через `git show`, а не доверяет изменённой версии кандидата. Обычные пути разрешены внутри `frontend/**` и отдельно `AGENTS.md`, `docs/PWA_RELEASE.md`. Запрещены backend/SQL/private/secret paths, symlinks и прочие нестандартные file modes. Изменения `frontend/release/**` и именованных workflow-файлов `.github/workflows/deploy-pages.yml`, `.github/workflows/code-validation.yml`, `.github/workflows/pwa-scope.yml` — **release controls**, им требуется PR автора GitHub ID `308028794` и отдельная строка в **body** этого PR:

`PWA-RELEASE-CONTROL: <40-character head SHA>`

SHA должен совпадать с текущим HEAD; следующий коммит аннулирует подтверждение. Не добавлять строку в чужой/непроверенный PR ради PASS. В `code-validation.yml` допускается менять только frontend-check block; остальные Writer/OIDC шаги обязаны оставаться побайтово прежними. Наш docs-only PR release controls **не меняет**, подтверждающая строка ему не нужна.

Отдельная попытка `pull_request_target` scope-workflow не дала действующей защиты, поскольку GitHub загружает workflow из default `main`. Его удалили из `pwa`; нельзя описывать его как активный required check. Новая строго доверенная проверка потребует отдельной архитектуры защищённого источника статуса и независимой приёмки; [Issue #50](https://github.com/Alexio00/HEALTH/issues/50) остаётся OPEN. Историческая опорная версия scope policy — `93964e3524171d789f03608958a6b0740bae23ee`.

## 4. Автоматический выпуск GitHub Pages

`.github/workflows/deploy-pages.yml` имеет имя **`Deploy HEALTH PWA`** и при `push` в `pwa` запускается только при изменении `frontend/**` или самого workflow; доступен отдельный `workflow_dispatch`. Документационный PR, меняющий лишь `frontend/README.md` и `docs/PWA_RELEASE.md`, **после merge затронет путь `frontend/**` и потому тоже запустит Pages**, если текущий workflow/фильтры не изменятся. Это не разрешает merge без отдельного `OWNER_GO`.

Группа `concurrency` — `pages-pwa` (`cancel-in-progress: true`), отдельная от прежней `main`. Публикация состоит из трёх jobs:

1. **`Verify PWA before release`** (`verify`): checkout кандидата, `node --check` для `frontend/app.js`, `frontend/sw.js`, `frontend/vaccination.mjs`, `frontend/supabase-client.js`; синтетические `frontend/tests/contract.mjs`, `sw.mjs`, `scope.mjs`, `release.mjs`; `python3 scripts/validation/public_secret_guard.py`; затем `node frontend/release/build.mjs "$RUNNER_TEMP/health-pages"` и upload одного `github-pages` artifact. Сборщик принимает только `GITHUB_REF=refs/heads/pwa` и `GITHUB_SHA`, равный проверенному Git HEAD.
2. **`Publish verified PWA`** (`deploy`): `needs: verify` и `github.ref == 'refs/heads/pwa'`, environment `github-pages`, разрешения `pages: write` и `id-token: write`. Обход проверки перед публикацией не предусмотрен.
3. **`Verify published release bytes`** (`postcheck`): `needs: deploy`; проверка через `node frontend/release/smoke.mjs` точного опубликованного SHA и файлов по HTTP. FAIL postcheck означает FAIL выпуска, даже если сам деплой завершился успешно.

Важно при ошибке: если artifact уже загружен в конкретный run, **не перезапускай** `verify`/весь run с повторным upload: дубликаты `github-pages` с тем же run ID могут сломать deployment. Либо перезапускай только deploy job при наличии единственного пригодного артефакта, либо запускай **новый** workflow run из `pwa`. Все действия — по текущим логам GitHub Actions; автоматического merge/rollback нет.

### Точная оболочка и кэш

Build собирает **15** перечисленных runtime-файлов во временный каталог runner, проставляет SHA в `index.html` и `sw.js` и создаёт `release.json` версии schema `1` (полный commit SHA + SHA-256 каждого runtime-файла). Тесты, release tooling, README и `RELEASE_CHECK.md` в опубликованный artifact не входят. Footer показывает короткий SHA **конкретного HTML**, а не потенциально более нового сервера.

Service worker использует кэш `health-shell-<full SHA>`. При установке запрашивает **8** разрешённых файлов оболочки с `redirect: error` и до `skipWaiting` проверяет коды ответа, MIME, cache policy и ожидаемые байтовые хеши. Полный кэш одной версии активируется целиком; ошибка CDN/неполная оболочка оставляет предыдущий worker. `updateViaCache: none` исключает опору на HTTP-кэш браузера для обновления worker. После activation старые `health-shell` кэши удаляются, прочие не трогаются; `controllerchange` инициирует одну контролируемую перезагрузку. Hash-маршруты читают тот же `index.html`.

Не кэшируются query string, `frontend/oauth-test/*`, OAuth consent, API/Supabase ответы, произвольные пути, Auth/Range запросы, redirects, non-200, неверный MIME и `private/no-store/no-cache`. **Offline shell ≠ offline медицинская карта.**

### Postcheck и ручная проверка

`Verify published release bytes` делает `no-store` HTTP-запросы к корню Pages, `release.json` и 15 runtime-файлам; проверяет status, MIME, точный SHA и SHA-256. Максимум **12** попыток с интервалом **10 секунд**; timeout одного запроса — **10 секунд**, timeout job — **5 минут**; `continue-on-error` отсутствует. Совпадение одного старого marker без совпадения байтов — FAIL. Postcheck обнаруживает неконсистентную публикацию, **не** откатывает её атомарно; при FAIL повреждённый релиз уже может быть доступен. Ориентир — статус workflow/уведомления Actions, без платных сервисов.

После успешного HTTP postcheck проверь в браузере маршрут, навигацию, отображение данных в **разрешённой** Auth-сессии, REC-ссылки, страницу вакцинаций, обновление/установку PWA. Это отдельная проверка: HTTP PASS не доказывает работу RLS, клинического UI, авторизованной сессии или установленного приложения. Не переносить реальные медицинские payload в логи/issue/evidence.

После выпуска ещё раз убедись, что `main` SHA, Supabase Writer accepted SHA, broker policy и runtime не изменены PWA-релизом. Не применяй прямые SQL updates для обхода контроля Writer.

## 5. Откат через защищённый PR

1. Найди ранее проверенный `pwa` commit и его свидетельства release/postcheck. Получи **актуальный** `pwa` и создай **новую** rollback-ветку от него; не делай remote reset или force-push.
2. Отмени только неисправное frontend-изменение. Для merge commit при необходимости: `git revert -m 1 <SHA>`. Разреши конфликты с текущими маршрутизатором, `frontend/oauth-test/*`, worker и release policy. Если обычный revert уберёт безопасный build/worker, восстанови только поражённые UI-файлы из проверенного дерева, оставив текущие средства выпуска.
3. Пересобери с нынешним tooling. Не копируй старые `release.json` или сгенерированный worker. Проверь весь diff; открой обычный PR в `pwa`. Release-control diff требует владельца и точной строки `PWA-RELEASE-CONTROL: <40-character head SHA>`. Дождись `static` с текущей базой; Ruleset не обходить.
4. Выполни независимый review и получи отдельный `OWNER_GO` на точный HEAD. После повторной проверки SHA/Ruleset/CI/обсуждений merge делается штатно: новый merge SHA означает **новую** версию релиза и кэша.
5. Дождись `Verify PWA before release` → `Publish verified PWA` → `Verify published release bytes`; сверяй реальный marker и все байты. Сначала осмотри публичную оболочку, затем только разрешённую авторизованную клиническую сессию. Сохрани синтетические offline route tests.
6. Неуспешная установка нового worker сохраняет старый. При успешном rollback worker переключает кэш и обновляет управляемые страницы; при необходимости закрой/открой PWA. Не очищай произвольно пользовательское/медицинское браузерное хранилище.
7. Если postcheck/rollback FAIL, сохрани evidence, останови неродственные релизы, найди причину в CDN/asset/build и подготовь **новый** штатный repair PR от живого `pwa`. При восстановлении не загружай второй `github-pages` artifact в прежний run ID.

Синтетический регрессионный набор строит две разные SHA-версии, проверяет обновление identities `index`/`worker`, отказ при устаревшем файле, отсутствие частично активированного кэша, ограниченные повторы и восстановление полной оболочки. Эта процедура не выполняет production rollback автоматически.

## 6. Проверка публичности Markdown и ссылок

`scripts/validation/public_secret_guard.py` **исключает `*.md`** из сканирования (`SKIP_SUFFIXES={".md"}`). Поэтому зелёный `static`/deploy guard **не подтверждает** безопасность Markdown. Перед PR/merge дополнительно вручную или независимым скриптом проверь **каждую** изменённую строку README и release guide: реальные имена/идентификаторы пациентов, полный REC, оригиналы Sources, приватные Drive URL/ID, cookies, Auth access/refresh tokens, пароли, DB URI, `sb_secret_*`, `service_role` key и любые медицинские значения. Термины, имена параметров и синтетические примеры сами по себе не секреты; секретные **значения** недопустимы.

Проверь относительные ссылки от местонахождения каждого Markdown и внешние GitHub/официальные ссылки. Не вставляй приватные ссылки на действующие Project State/Manual в публичный README. Публичная документация должна ссылаться на `AGENTS.md`, текущий `docs/PWA_RELEASE.md` и существующие Issues/PR; исторические англоязычные аудиты остаются историческими свидетельствами, переводить их для этого выпуска не нужно.

## 7. Координация и пределы PWA-only работ

- Перенос любых изменений из другого PR допускается лишь после точного сравнения с живой `pwa`. Открытые на момент подготовки этой процедуры соседние PR и старые release branches — **не нормативный список** и не право на merge/delete. Обязательно повторно читать GitHub.
- Нельзя сливать Writer-ветки и их `frontend/**` файлы в `main` «для публикации Pages». Старый Pages workflow на `main` и его отдельное удаление относятся к main/Writer acceptance.
- Изменения OAuth/consent, `frontend/supabase-client.js`, service worker, build/release tooling и GitHub Actions требуют отдельного security/threat-review, даже если находятся в `frontend/**`. Визуальные read-only изменения на **существующей** модели можно выпускать независимо от разработки нового Writer.
- Draft [PR #51](https://github.com/Alexio00/HEALTH/pull/51) и [PR #59](https://github.com/Alexio00/HEALTH/pull/59) нельзя считать готовыми к выпуску зависимых медицинских сущностей только по UI тестам: отделяй безопасную визуальную часть. [Issue #62](https://github.com/Alexio00/HEALTH/issues/62) — граница Writer-impact.
- Полная будущая изоляция Writer требует отдельно принятого immutable Writer ref/repository, аудита доверия и единовременного контролируемого повторного принятия. Это **предложение**, не действующая production-архитектура. [Draft PR #76](https://github.com/Alexio00/HEALTH/pull/76) — проектная документация; завершённый/параллельный [PR #92](https://github.com/Alexio00/HEALTH/pull/92) в рамках этой задачи **не изменяется**.
- Активная процедура — решение владельца от 14.10.2026 в Project Manual, раздел о **приёмке технических GitHub-изменений по точному SHA**. Исторические английские аудиты, migration snapshots и прежние PR не являются разрешениями на текущие действия.

Справка GitHub о доверии к `pull_request_target`: https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target
