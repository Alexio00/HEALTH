# HEALTH Scheduler — ручной эксплуатационный контроль (временная политика)

**Решение Product Owner: 14.10.2026 — пока ручной контроль, без внешнего watchdog.**

**Статус:** операционная инструкция-кандидат; не установлен автоматический SLA и не разрешён production cutover. Этот текст не заменяет действующие приватные HealthDB Project State и Project Manual. Все проверки — read-only; **никаких** manual `workflow_dispatch`, синтетических production FAIL, реальных backup/restore, изменения Secrets, Variables или `scheduler` commits.

## 1. Что проверять и когда

**Рекомендуемая периодичность:** ежедневно после окна ожидаемых GitHub runs; время проверки оператор выбирает по фактическому `run_started_at`, поскольку GitHub может задержать расписание на часы. Это не нормативный дедлайн. Раз в неделю сверять 7 календарных дней и различие между legacy backup и новым complete backup.

**Действующий production** на дату инвентаризации: `Alexio000/SHEDULLER/main`, SHA `8656a360c2b24c0f51e6e2b80edf78e6bd89ccc4`. При новом SHA сначала определить действующий принятый pin; не считать новый main автоматически принятым. `HEALTH/main` Writer accepted SHA `3409791f1ffc5749020e7ff07139b0cec722f6fc`; новый Scheduler в HEALTH **не активирован**.

| Контроль | Ожидаемое schedule (UTC / Москва) | Workflow | Проверять |
|---|---|---|---|
| Ежедневный backup | 00:00 / 03:00 | SHEDULLER `.github/workflows/daily-backup.yml` | `event=schedule`, `head_branch=main`, exact expected commit SHA, `conclusion`, **jobs**, подтверждение ACTIVE/recovery отдельно |
| Read-only keepalive | 00:37 / 03:37 | SHEDULLER `.github/workflows/keepalive.yml` | `event=schedule`, exact expected SHA, job `keepalive=success`, запрет считать это доказательством backup |
| Новый 15-дневный heartbeat | 05:17 / 08:17 | HEALTH Draft #72 `health-activity.yml` | **Не учитывать как production** до отдельного принятия и активации |
| Новый 18-дневный watchdog | 08:43 / 11:43 | HEALTH Draft #72 `health-activity.yml` | **Не учитывать как production**; не гарантирует доставку при полном выключении GitHub schedule |

### Разница между результатами

- `WORKFLOW_SUCCESS`: только факт завершения GitHub; недостаточно для полноты бекапа.
- `LEGACY_BACKUP_STAGES_SUCCESS`: jobs `database`, `sources`, `verification` = success, но **без** job `complete`; это не доказательство full CompleteSets pipeline.
- `COMPLETE_JOB_SUCCESS_UNVERIFIED`: job `complete` success, но независимая приватная проверка remote ACTIVE/recovery proof не проведена.
- `BACKUP_VERIFIED`: помимо complete run отдельно прочитан и проверен в **приватном** контуре единственный ACTIVE, producer SHA, SHA256 remote bytes, Auth/roles/все Sources и полный recovery receipt; такой статус нельзя назначать только по GitHub metadata.
- `KEEPALIVE_RUN_SUCCESS`: отдельная техническая активность, без выводов о свежести архива.
- `RUN_MISSING`: для конкретного календарного дня нет `event=schedule` run. `workflow_dispatch`, `pull_request`, `push` этот пробел не закрывают.
- `RUN_FAILED_OR_INCOMPLETE`: failed, cancelled, timed_out, action_required либо skipped-only; выводить честный статус, не делать auto-retry.
- `SHA_UNACCEPTED`: running commit отличается от принятого pin, даже при success.
- `RECOVERY_OR_ROTATION_AMBIGUOUS`: два ACTIVE, смешанные CANDIDATE/UPLOADING, посторонний producer или неизвестное состояние journal.
- `NOT_VERIFIED`: не было прав или evidence для конкретного контроля; **не** превращать в «нет проблемы».

### Порядок одной проверки

1. Сверить current GitHub branch HEAD для `SHEDULLER/main`, `HEALTH/main`, `HEALTH/scheduler-code` с принятым для каждого компонента SHA (не переносить pin между разными ветками). Не менять Variables.
2. Открыть Actions run history SHEDULLER и **отфильтровать event=schedule**. По каждой из двух активностей найти run за проверяемую календарную дату *в UTC*. Если запись отсутствует за рассматриваемые UTC-сутки, проверить соседние сутки: сильная задержка GitHub может перенести `created_at` через полночь и сделать привязку к плановому cron-слоту неоднозначной. До корреляции ставить `MISSING_OR_CROSS_DAY_UNCONFIRMED`; не ждать встроенного failed email.
3. Зафиксировать `run_id`, `run_attempt`, `event`, `head_sha`, `created_at`, `run_started_at`, `completed_at`, `conclusion`, actor. Не смешивать manual rerun и scheduled run.
4. Backup: раскрыть **job statuses**. `complete=success` при `database/sources/verification=skipped` — ожидаемая ветка нового full pipeline. Если работают legacy stages без `complete`, отметить другой тип резервирования. Зелёный run не подтверждает «полный complete».
5. Только при уполномоченном доступе к приватным evidence отдельно проверить состояние Backup Health: один ACTIVE, идентичность/целостность remote archive, независимый full DB/Auth/roles/Sources restore receipt и единый Writer/backup lock. **Не скачивать** архив в обычный публичный контур и не выводить IDs/медицинские строки/логи в GitHub.
6. Keepalive: проверить ожидаемые read-only jobs и завершение. Не выполнять вручную SQL, даже SELECT, только ради этого мониторинга.
7. Сопоставить план и фактический старт. Задержку указывать числом в минутах, без автоматического вердикта «просрочен» — утверждённого порога пока нет.
8. Если что-то не проверено, записать конкретное поле `NOT_VERIFIED`. Не заменять отсутствие evidence текстом `PASS`.
9. При FAIL/UNKNOWN: создать или обновить технический инцидент (без приватных деталей), уведомить владельца через текущий разрешённый канал. **Не** перезапускать backup/rotation/restore или менять секреты без отдельного GO.

## 2. Отчёт одной проверки (только безопасные технические метаданные)

```text
Observation UTC: YYYY-MM-DDTHH:MM:SSZ
Scope: SHEDULLER production only / HEALTH draft excluded
Scheduled date UTC: YYYY-MM-DD
Backup: run_id=..., event=schedule, branch=main, SHA=..., type=complete|legacy|unknown,
        job_conclusion=..., delay_min=..., classification=...
Private archive: ACTIVE_count=VERIFIED|NOT_VERIFIED, digest=VERIFIED|NOT_VERIFIED,
                 full_restore=VERIFIED|NOT_VERIFIED (no locator/payload)
Keepalive: run_id=..., event=schedule, SHA=..., job_conclusion=..., delay_min=...
Manual operator: verified metadata only; email delivery=NOT_VERIFIED unless independently checked
Decision: NO_ACTION|READ_ONLY_RECONCILIATION|OWNER_GO_REQUIRED
```

## 3. Негативные случаи и запреты

| Ситуация | Что делать | Чего не делать |
|---|---|---|
| Нет запуска за день | Фиксировать `RUN_MISSING`, проверять статус GitHub workflow/активность репозитория | Не считать отсутствие failure-email успехом |
| Run success, но archive proof недоступен | `COMPLETE_JOB_SUCCESS_UNVERIFIED` | Не сообщать `BACKUP_VERIFIED` |
| Старый SHEDULLER получил новый main SHA | Проверить `HEALTH_COMPLETE_BACKUP_COMMIT` как **имя** действующего pin и известную процедуру acceptance; может вызвать FAIL полного backup job | Не обновлять variable самовольно, не подменять accepted SHA |
| Failed complete / нет новых ACTIVE | Зафиксировать технический инцидент; отдельный read-only reconciliation | Не запускать второй backup и не отправлять старый архив в Trash |
| Unknown UPLOADING/CANDIDATE | Сохранить прежний ACTIVE, owner-only план и отдельная reconciliation | Не делать blind retry, cleanup, quarantine или activate |
| Writer/backup SQL lock занят | Backup должен отказывать/ожидать по принятому контракту | Не отключать lock и не выполнять writer/SQL обход |
| Несколько репозиториев с включённой ротацией | Release NO-GO до подтверждения pause и zero in-flight; весь межрепозиторный путь под архитектурным контролем | Не надеяться на GitHub concurrency |
| Прекратились оба cron | Обнаруживать только внешним ручным наблюдением, так как внутренний watchdog тоже не работает | Не обещать автоматический email |
| Heartbeat branch свежая от чужого commit | `HEARTBEAT_UNPROVEN`; issue #82 | Не считать дату HEAD доказательством доверенного job |
| После реального restore Writer | Сохранить Writer disabled, требуется новое отдельное acceptance | Не включать Writer автоматически |

## 4. Контроль почтовых уведомлений

Для scheduled runs 14.10.2026 оба GitHub API `actor` и `triggering_actor` показывают `Alexio000`. Это **не доказательство**, что письма реально доставляются владельцу либо что включены все настройки уведомлений. В рамках ручного режима проверять фактическое получение уже возникших штатных ошибок/предупреждений; искусственный FAIL в production запрещён.

Нельзя ни подразумевать, ни утверждать, что GitHub гарантирует сообщение об отсутствии запуска. Отсутствие scheduled run — наблюдаемый вручную факт.

## 5. Исторический контрольный срез (не production SLA)

`event=schedule`, даты UTC 08–14.10.2026: backup **7/7** workflow success, при этом 08–12.10 были только legacy jobs `database/sources/verification`, а 13–14.10 — full `complete` jobs; keepalive **7/7** success. Фактическая задержка от номинального cron: backup 168.8–449.8 минут (медиана 437.5); keepalive 282.1–386.2 минут (медиана 350.5). Эти цифры не доказывают доступность/полноту конкретного архивного комплекта.

Один пример: backup run [38502989091](https://github.com/Alexio000/SHEDULLER/actions/runs/38502989091), keepalive run [38515980080](https://github.com/Alexio000/SHEDULLER/actions/runs/38515980080), 14.10.2026.

## 6. Когда менять эту политику

Только после отдельного решения владельца с указанием ответственного за ручную проверку, желаемого эксплуатационного срока реакции/порогов и, при необходимости, будущего независимого мониторинга. Сейчас внешний watchdog = **NOT SELECTED**, никаких автоматизаций не создаётся.

Связанные документы: [Scheduler runbook Draft #86](https://github.com/Alexio00/HEALTH/pull/86), [main launchers #89](https://github.com/Alexio00/HEALTH/pull/89) (замена старого #72), [итоговый executable #90](https://github.com/Alexio00/HEALTH/pull/90) (замена исторических #73/#81/#88), [#65](https://github.com/Alexio00/HEALTH/issues/65), [#82](https://github.com/Alexio00/HEALTH/issues/82), [#87](https://github.com/Alexio00/HEALTH/issues/87).
