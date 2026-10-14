# Scheduler HEALTH — эксплуатационный runbook и сценарии отказов

**Статус: DRAFT / технический проект, не утверждённый SLA, не разрешение на production.**
Срез 14.10.2026. Ответственный контур — Scheduler Operations. Клинические данные и секреты не включать в GitHub. Этот документ не меняет Project State, Project Manual, Writer и текущие расписания.

## Источники истины и роли

- Действующий PRIVATE HealthDB Project State + Project Manual имеют приоритет над этим runbook. Их актуальность проверять перед release.
- Production Writer — `HEALTH/main`, принятый SHA на дату среза `3409791f1ffc5749020e7ff07139b0cec722f6fc`; любые изменения `main` требуют повторного Writer acceptance.
- Production расписания: `Alexio000/SHEDULLER/main`, SHA `8656a360c2b24c0f51e6e2b80edf78e6bd89ccc4`. Не изменять до отдельного cutover GO.
- Исполняемый код нового Scheduler: Draft [#73](https://github.com/Alexio00/HEALTH/pull/73), цель `scheduler-code`. Только workflow launchers: Draft [#72](https://github.com/Alexio00/HEALTH/pull/72), цель `main`.
- `scheduler`: ТОЛЬКО пустые служебные коммиты после принятия heartbeat; никакого исполняемого кода, статусов медицинских записей или deployment.
- Writer и backup capture используют общий SQL exclusion boundary. Repo-local GitHub concurrency **не обеспечивает** межрепозиторную взаимную блокировку ротации Google Drive.
- Названия environment variables, workflow/run IDs и SHA допустимы в публичной технической документации; значения секретов, Source locators, архивы, медицинские записи и private recovery evidence — нет.

## 1. Карта активностей

| Активность | Текущий production / предлагаемый исполнитель | Время (UTC) | Условия | Критерий успеха |
|---|---|---|---|---|
| Daily complete backup | SHEDULLER/main; после отдельного GO HEALTH/main launcher + immutable scheduler-code | 00:00 ежедневно = 03:00 МСК | Точный принятый SHA, один исполнитель, SQL lock, restricted reader, verified destination | Запуск complete job + remote byte readback + полный recovery + ровно один ACTIVE |
| Supabase keepalive | SHEDULLER/main; в перспективе HEALTH/main launcher | 00:37 ежедневно = 03:37 МСК | Read-only роль/запрос, CA/TLS, принятый код | Успешное read-only соединение и проверка роли |
| Heartbeat (только Draft) | HEALTH/main launcher → scheduler-code JS → branch scheduler | 05:17 ежедневно | Включённый trusted launcher, точный code pin, >=15 суток с *валидного* heartbeat | Доказанный принятый workflow run + только разрешённый пустой commit |
| Overdue watchdog (только Draft) | HEALTH/main launcher → scheduler-code JS | 08:43 ежедневно | Точный pin; read-only job | FAIL при >=18 суток; событие инцидента фиксируется даже при последующем восстановлении |
| Manual preflight/candidate/activate/quarantine (Draft) | HEALTH/main owner-only workflow → scheduler-code | Не scheduled | Owner-only, accepted SHA и release gates, старый runner paused и idle | Remote readback, independent full recovery, exact candidate digest, journal reconciliation |

Основное ограничение: GitHub `schedule` существует только в default branch, может сработать поздно либо не сработать. «Run success» не равен «архив подтверждён»; «нет failed runs» не равен «не было пропусков».

## 2. Ежедневная read-only проверка

1. Посмотреть реальные GitHub Actions runs в **действующем** SHEDULLER: событие `schedule`, branch `main`, ожидаемый workflow/producer SHA, `created_at`, `run_started_at`, `completed_at`, `conclusion`. Не путать с ручными и PR-triggered runs.
2. Для backup посмотреть jobs: основной `complete` должен иметь `success`; legacy `database/sources/verification` могут быть `skipped` при включённом complete-mode. Проверить, что шаг полного remote readback/recovery/rotation завершён `success`.
3. В уполномоченном **приватном** контуре, когда доступно, проверить возраст последнего ACTIVE, producer SHA, digest и independent recovery receipt. При отсутствии доступа записать `ARCHIVE_NOT_VERIFIED`, а не `PASS`. Не выводить ID/bytes/manifest/logs Sources в публичный GitHub.
4. Проверить отдельный keepalive run и его read-only шаг. Его успешность не компенсирует отсутствие backup.
5. Сравнить с графиком и зарегистрировать даже пропущенный запуск, если GitHub не создал run. Несколько часов задержки не интерпретировать как FAIL без утверждённого SLA, но сохранять фактическое отклонение.
6. Контролировать текущую версию `HEALTH/main` и `SHEDULLER/main`. Если SHA изменился, сравнить с принятым exact-SHA pin и проверить способность очередного scheduled job стартовать; никаких автоматических обновлений pin.

**Предлагаемые (НЕ утверждённые) значения:** backup freshness warning по достижении 36 часов без нового верифицированного ACTIVE, incident по достижении 48 часов; keepalive incident после двух пропущенных ожидаемых runs. До owner acceptance отмечать `SLA_UNSET` и эскалировать факт просрочки/неизвестности без применения этих порогов как действующей политики.

### Минимальные поля private operational evidence

`observation_utc, repo, branch, workflow, event, run_id, run_sha, expected_sha, planned_utc, started_utc, completed_utc, conclusion, archive_state, archive_freshness, recovery_receipt_present, lock_status, notification_state, owner_action_required`.

В публичный issue можно передавать статус/безопасные run IDs и общие SHA; **не** передавать полный recovery report, connection/Drive locators и метаданные медицинских Sources.

## 3. Состояния мониторинга и реакция

- `OK_VERIFIED`: expected immutable SHA, реальный production run, job success, private archive+recovery evidence проверены. Только для backup с доступным independent receipt.
- `RUN_SUCCESS_UNVERIFIED`: GitHub run успешен, но содержимое/возраст ACTIVE/recovery evidence не проверены. Это **не** `OK_VERIFIED`.
- `DELAYED`: run начат после cron; регистрировать длительность и проверять SLA, если утверждён.
- `MISSING_RUN`: к ожидаемому окну run не создан; `failure email` сам по себе не сработает.
- `JOB_FAILED`: run/job создан и завершился fail/cancel/timeout. Не повторять backup без reconciliation.
- `STATE_AMBIGUOUS`: несколько ACTIVE/CANDIDATE, неполный UPLOADING, lost PATCH без точного readback, чужой producer, неизвестный source/recovery state.
- `HEARTBEAT_UNPROVEN`: ветка свежая, но origin служебной активности не подтверждён; запрещено засчитывать как доказанный надёжный механизм.
- `SCHEDULE_STOPPED`: нет runs, workflow disabled или GitHub actor недоступен; in-repo watchdog тоже может молчать.

### Реакция на backup FAIL / UNKNOWN

1. **Не запускать** повторное создание архива/ротацию/Trash или restore на production автоматически.
2. Read-only проверить SHA и runtime статус; приватно установить ровно один текущий ACTIVE, наличие CANDIDATE/UPLOADING и journal state.
3. Если `STATE_AMBIGUOUS`, остановить любые release/rotation: отдельно оформить точный план reconciliation и решение владельца. Не скрывать неполные orphan, не менять старый ACTIVE.
4. После доказанного восстановления разрешить следующую операцию только через штатный bounded/owner-reviewed путь.
5. После restore Writer остаётся disabled до отдельного acceptance; recovery не является разрешением на клинические записи.

### Реакция на keepalive/heartbeat

- Failed keepalive: проверить только технические логи/роль/CA/TLS и run type; без самостоятельной записи в Supabase.
- Heartbeat due (>=15 дней): разрешать только verified accepted launcher; branch HEAD age сама по себе не доказывает успешность workflow. Посторонние коммиты должны быть инцидентом, а не reset таймера.
- Heartbeat overdue (>=18 дней): сохранить исторический overdue incident даже если remediation push успешен. Текущий Draft JS после push выдаёт FAIL по состоянию **до** push; контракт уведомления следует формализовать в [#82](https://github.com/Alexio00/HEALTH/issues/82).
- Если оба GitHub cron перестали исполняться, in-repo check не уведомит. До отдельного решения достаточно ручной проверки run history; внешний мониторинг не добавлять автоматически. Ни коммиты в non-default `scheduler`, ни `schedule` не доказаны защитой от 60-дневной деактивации GitHub.

## 4. Получатели уведомлений

Существующий механизм — GitHub Actions notifications, включая email при failure в настройках пользователя, который выступает actor расписания. Этот получатель не равен гарантированному адресату владельца. Проверить по текущему actor/cron-change history и **фактической доставке** в безопасной санкционированной пробе, не создавая искусственные production failures.

Если GitHub не создал run, штатное `on failure` email отсутствует. `MISSING_RUN` и `SCHEDULE_STOPPED` требуют независимого наблюдения/ручной проверки, а не новых скриптов с доступом к секретам. Ручная проверка не является автоматическим SLA.

## 5. Предохранители cutover (пока NO-GO)

1. Exact `main` SHA принят в Writer broker/runtime; exact `scheduler-code` executable SHA принят независимым ручным review; full diff и GitHub Rulesets перепроверены непосредственно перед merge.
2. Доверенные launchers #72 отдельно проверены на `event/ref/actor`, checkout immutable SHA, отсутствие исполнения untrusted PR кода с секретами, Environment/role restrictions, public log/artifact boundaries и `contents:write` heartbeat.
3. Старый SHEDULLER production **остановлен и доказано zero in-flight jobs** до первой новой записи (включая UPLOADING); owner подтверждает это отдельно. GitHub concurrency не заменяет этот шаг.
4. Выполнить и проверить новым кодом single CANDIDATE + remote byte readback + independent full DB/Auth/roles/Sources recovery, без ротации старого ACTIVE.
5. Owner отдельно принимает candidate digest и даёт GO на `activate`; повторный `DONE` или потерянный PATCH обрабатывается только exact readback, без повторного Trash.
6. Запуск нового daily и keepalive по отдельному GO, контроль двух последовательных **реальных scheduled** запусков и recovery evidence. Только затем считать новый Scheduler production и обсуждать вывод SHEDULLER из эксплуатации.
7. При rollback к SHEDULLER сначала reconcile новый CANDIDATE/UPLOADING/journal; никогда не включать старый runner поверх неясного чужого состояния.

Никакой из этих пунктов не предоставляет разрешение на текущий merge/dispatch, перенос Secrets, включение флагов или реальный backup.

## 6. Синтетические сценарии приёмки (не доказаны данным документом)

| ID | Вход | Требуемое поведение |
|---|---|---|
| HB-01 | возраст 14.99/15/17.99/18 дней | без push до 15, due с 15, overdue с 18 |
| HB-02 | чужой/ручной commit в `scheduler` с новой датой | событие не выдаётся за принятый heartbeat, возраст не сбрасывается без proof |
| HB-03 | чужой author/message, rewrite history, absent branch, future clock >300 сек | fail closed, никаких push |
| HB-04 | overdue 19 дней, затем успешный service push | явно отличать remediation success от incident notification |
| HB-05 | оба schedule вообще не исполняются | false claim о доставленном failure email запрещён; manual/external observation |
| BK-01 | Writer удерживает конфликтующий lock | capture не выполняется, медицинские данные неизменны |
| BK-02 | SHEDULLER и HEALTH обращаются к одной rotation state | NO-GO, нет двойного Trash, нет необъявленного ACTIVE |
| BK-03 | полностью переданный UPLOADING, lost upload response | exact byte readback, допускается единственное idempotent resume |
| BK-04 | неполный orphan, ambiguous candidates, чужой SHA | fail closed, owner-only quarantine без auto-trash |
| BK-05 | восстановление неполно: Auth/roles/Source digest mismatch | не promote ACTIVE; предыдущий архив сохраняется |
| BK-06 | повторный activate после DONE/потерянный marker PATCH | reconciliation без повторной ротации |
| BK-07 | stale/unreviewed scheduler SHA, unaccepted main, missing trusted source | secret-consuming job не исполняет кандидата |
| OBS-01 | успешный Actions job при отсутствии archive proof | `RUN_SUCCESS_UNVERIFIED`, не `OK_VERIFIED` |
| OBS-02 | workflow пропущен и отсутствует failed run | `MISSING_RUN`, нельзя считать отсутствие email здоровым состоянием |
| NOT-01 | тестовый failure в отдельно разрешённом безопасном контуре | документировать получателя и реальную доставку, без production backup-fail injection |

Исполнение тестов, замеченные результаты и evidence должны быть привязаны к exact-SHA кандидата. Для кодовых исправлений отдельная задача Scheduler Code, для Release/Writer/external monitor — архитектурный координатор.

## 7. Открытые блокеры и связанные задачи

- [Scheduler Code #82](https://github.com/Alexio00/HEALTH/issues/82): ложная свежесть heartbeat, trusted evidence и overdue semantics.
- [Architecture #65](https://github.com/Alexio00/HEALTH/issues/65): safe backup consolidation, single-archive cutover и межрепозиторная координация.
- [HIGH #50](https://github.com/Alexio00/HEALTH/issues/50): доверенный required status issuer отсутствует; действующая ручная exact-SHA приёмка не превращает CI в trusted security gate.
- Draft [#72](https://github.com/Alexio00/HEALTH/pull/72) / [#73](https://github.com/Alexio00/HEALTH/pull/73): не объединять со старыми #64/#71, не допускать двух независимых реализаций heartbeat.
- [GitHub schedule semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [notifications](https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs), [scheduled workflow disabling](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/disabling-and-enabling-a-workflow).

**До отдельного независимого exact-SHA review и owner GO: документация/синтетика בלבד, Production Scheduler — NO-GO.**
