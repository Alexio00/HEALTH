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
