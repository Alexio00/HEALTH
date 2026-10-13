# Консолидация Scheduler в HEALTH — подготовка и приёмка

**Режим:** Draft, без production cutover. Действующий SHEDULLER выполняет backup и keepalive до отдельного подтверждённого переключения.

## Архитектура, решение владельца 13.10.2026

| Ветка | Роль |
|---|---|
| `main` | Принятый Writer и только минимальные доверенные расписания/ручные launchers |
| `pwa` | Интерфейс, публикация GitHub Pages |
| `scheduler-code` | Backup, recovery, Supabase keepalive, heartbeat и синтетические тесты |
| `scheduler` | Только служебные 15-дневные пустые коммиты |

Код Scheduler принимается отдельным PR в защищённую `scheduler-code`. В `main` запускать его только по утверждённому полному immutable commit SHA, а не по branch HEAD. Изменение executable SHA требует новой приёмки Scheduler, не изменяя само по себе код Writer. Добавление launchers в `main` меняет Writer accepted code SHA и возможно только в согласованном релизе Writer. Production workflow ни при каких условиях не берутся из недоверенного PR.

## Границы поставки

Этот кандидат содержит исполняемые `scripts/scheduler/**`, `scripts/automation/supabase_keepalive.py`, `scripts/automation/health_activity.mjs`, тесты и документацию. Все workflows резервного копирования, активации, preflight, keepalive и heartbeat должны находиться **только в отдельном launcher PR #72** (для одноразовой активации — отдельная будущая оценка) и после принятия — в `main`. Единственный GitHub Actions workflow в этом PR — синтетическая проверка без секретов. Она не является независимой обязательной проверкой безопасности.

Действующий `Alexio000/SHEDULLER` сохраняется как приватный исполнитель. Не удалять историю, backup или оригиналы, не переносить приватные Drive IDs, имена Sources, payload, credential URLs, RCLONE_CONFIG и секреты в публичный GitHub. Приватные переменные/Secrets передаются только через разрешённые Environments и только после отдельного решения владельца.

## Регулярные функции

- Complete backup: cron `0 0 * * *` UTC (03:00 МСК), захват PostgreSQL/Auth/ролей и всех Sources, контроль целостности, полное изолированное восстановление и ротация одного ACTIVE после проверки. Один `pg_dump` не считается полным backup.
- Supabase keepalive: cron `37 0 * * *` UTC (03:37 МСК), отдельная роль `health_backup_reader` и CA-pinned TLS, только read-only запрос.
- GitHub heartbeat: ежедневная проверка с пустым коммитом в `scheduler` при возрасте ≥15 дней и failure при ≥18 днях. GitHub не гарантирует, что активность только в non-default branch предотвратит отключение schedule через 60 дней. Внутренний watchdog не обнаружит полное прекращение работы расписаний.

`scheduler-code` и `scheduler` нельзя использовать взаимозаменяемо. Нельзя выдавать heartbeat token права записи в `main`, `pwa` или `scheduler-code` как намеренную функцию; `GITHUB_TOKEN` с `contents:write` технически выдаётся на репозиторий, поэтому конечное ограничение прав требует проверки GitHub Rulesets, а не только проверки целевого ref внутри Node-скрипта.

## Защита и аудит до merge

1. Защитить `scheduler-code` от force push, удаления и прямых изменений, обязать контролируемый PR. Проверить GitHub Free Rulesets и их фактическое применение.
2. Создать доверенную проверку security scope **вне изменяемого PR**. Текущий candidate workflow сам по себе недостаточен: см. [HIGH #50](https://github.com/Alexio00/HEALTH/issues/50).
3. Отдельно проверить все `main` launchers (#72): checkout по полного SHA, отсутствие исполнения кода PR с secrets, owner guard, Permissions, event/ref, Environment restrictions, закрытые журналы/артефакты, ограничение manual activation.
4. Провести полный privacy-аудит включая историю публикуемых коммитов и все module outputs; простой grep по email/Drive ID не заменяет такого аудита.
5. Повторить синтетические негативные сценарии (подмена producer SHA, candidate provenance/digest, роль/CA, Sources consistency, failed upload/rotation, старый ACTIVE, неисправное восстановление).
6. Отдельно доказать реальное восстановление нового архива в разрешённом приватном контуре. Зелёный CI не означает эксплуатационный GO.

## Протокол будущего переключения (НЕ РАЗРЕШЁН этим документом)

- Проверить последнюю ACTIVE копию SHEDULLER и возможность восстановления.
- Выполнить ручной preflight и отдельный full restore новой версии без конкурирующей ротации.
- Утвердить immutable executable SHA и минимальные ограниченные credential roles, проверить настройки защищённых Environments.
- Согласовать Writer main SHA reacceptance при выпуске #72 и HIGH scope controls.
- Запросить отдельную авторизацию владельца на момент cutover/rotation. GitHub concurrency не защищает от двух разных репозиториев: выключение старых jobs и завершение всех in-flight runs обязательно.
- Включать HEALTH backup/keepalive по одному, проверить восстановление и минимум два успешных последовательных scheduled runs; затем только архивировать SHEDULLER с отключёнными Actions.
- Уточнить действующие Project State/Manual после подтверждённого перехода. Не объявлять подготовленный код уже работающим.

Связанные задачи: [HEALTH #65](https://github.com/Alexio00/HEALTH/issues/65), [#50](https://github.com/Alexio00/HEALTH/issues/50), [#69](https://github.com/Alexio00/HEALTH/issues/69). Launchers: [Draft PR #72](https://github.com/Alexio00/HEALTH/pull/72). Исторические варианты: #64/#67/#70/#71.

## Предохранитель разового переноса (пока Draft)

Кандидатный `cutover_guard.py` отказывает `candidate`/`activate`, если не подтверждены: точный принятый Writer/main SHA, точно принятый checkout SHA Scheduler, доверенный main-only ручной workflow владельца, два независимых owner-asserted gate флага (`HEALTH_INREPO_RELEASE_ENABLED=true` и `HEALTH_LEGACY_BACKUP_PAUSED=true`), а также ручная фраза `LEGACY_SHEDULLER_PAUSED_AND_IDLE`. Новый daily backup должен оставаться выключенным во время этой процедуры. Эти флаги **не доказывают фактическое отсутствие запуска в SHEDULLER** — владелец должен вручную проверить состояние Actions и последний complete ACTIVE до установки флагов. Кандидатный запуск тоже загружает архив в общую папку `CompleteSets`: его нельзя выполнять, пока старый SHEDULLER работает.

`activate` запрещён без ранее созданного `CANDIDATE`; после запуска `candidate` необходим review полного независимого восстановления. Если понадобится откат к старому Scheduler после появления нового `CANDIDATE`, сначала отдельно согласовать и безопасно разрешить чужой candidate/journal: старый runner может подобрать его при следующем запуске. Не включать SHEDULLER вслепую. Запуск release workflow добавляется в Draft PR #72 и не внедрён в main. Правила CI и реальный cutover остаются отдельной приёмкой.

В следующем ручном запуске `activate` дополнительно требуется точный `HEALTH_RELEASE_CANDIDATE_SHA256` (64 hex) из проверенного статуса предыдущего `candidate`; код сверяет его с облачным кандидатом *до* ротации. В публичный workflow вводится **только digest**, но не Source ID, оригинал или приватный Drive locator. Пустой/чужой digest блокирует активацию.


## Исправление B-02 / H-04 (Draft, synthetic only)
- У нового backup ZIP до завершения передачи и SHA-256 byte-readback состояние `UPLOADING`, не `CANDIDATE`. Только подтверждённая загрузка становится CANDIDATE. Единственный orphan UPLOADING нового producer можно повторно проверить через `candidate`; неполный/чужой архив, несколько кандидатов или неоднозначное состояние требуют ручной private exact-ID сверки, без дубликатов, автоматического Trash либо ротации.
- `activate` допускает идемпотентное завершение после journal DONE только для того же ACTIVE ID, принятого SHA-256, producer SHA и повторного реального полного восстановления. При потерянном ответе PATCH marker выполняется readback. Уже завершённая ротация не повторяет Trash; новый архив не создаётся.
- При cutover старый SHEDULLER должен быть остановлен до первой записи в общую папку, включая UPLOADING. Подтверждение production rollback, Environments/Secrets и независимая приёмка кода остаются обязательными.
