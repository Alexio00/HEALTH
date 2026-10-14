# Актуальная документация и границы доказательств

## Карта ответственности и статуса на 14.10.2026

Это навигация по **действующим техническим текстам**, а не самостоятельный источник клинических полномочий. Приоритет: прямое решение владельца → живые приватные Project State/Manual → принятый Writer contract и фактический runtime. Технические предложения в Draft PR не переписывают принятые правила.

| Раздел | Принято сейчас | В разработке, не выпуск |
|---|---|---|
| Writer | `main` с неизменяемым принятым кодовым SHA; отдельные bounded Writer/Verifier/Validation | `writer-code`, Gateway #84 и проект разделения релизов #76 |
| PWA | защищённая `pwa`, read-only SQL, Pages, required `static` | UI #80/#85; #59 ждёт модель вакцинаций |
| Scheduler | действующий приватный SHEDULLER с проверяемой ACTIVE-копией и restore | `scheduler-code` (#73/#81/#88), служебный `scheduler`, launchers #72/#89, operations #86 |
| Схема | принятые `supabase/migrations` и ограниченный Writer allowlist | вакцинации #45 и проверка совместимости #62 |
| Защита релизов | отдельный ручной независимый exact-SHA review и owner GO | trusted scope #78: R3 NO-GO, HIGH #50 остаётся открытым |

**Пятиветочная схема:** `main`, `writer-code`, `pwa`, `scheduler-code`, `scheduler`. Новые `writer-code` / `scheduler-code` являются линиями разработки, а не новым принятым production. Дополнительного постоянного архитектурного branch нет. Четыре чата работают независимо и направляют общий schema/Auth/Writer/control-plane handoff архитектору согласно [техническому Draft #83](https://github.com/Alexio00/HEALTH/pull/83). Это организационный Draft, не прямое изменение приватного Manual.

**Важно для документационных PR:** merge в `main` меняет принятый Writer SHA; требуется самостоятельная процедура нового code acceptance, включая проверку GitHub broker/runtime policy, а не только успешный Docs CI. Исторические материалы оставлять в первоначальном виде; не превращать старые формулировки вроде «Writer disabled» или «Drive canonical» в текущую операционную инструкцию. Никаких реальных REC, private Source IDs, прямых закрытых ссылок и секретов в публичном репозитории.

## Что ещё не оформлено как действующее руководство

- **Русские руководства** — [Issue #61](https://github.com/Alexio00/HEALTH/issues/61): переводить только рабочие инструкции. Исторические англоязычные аудиты оставлять как свидетельства; отдельный PWA-контур обновляет свой `frontend/README.md`.
- **Установка для нового пациента** — [#53](https://github.com/Alexio00/HEALTH/issues/53), затем [#54](https://github.com/Alexio00/HEALTH/issues/54): отдельная среда, полная ручная схема и только затем безопасная автоматизация. Текущий README не заменяет установочную инструкцию.
- **Надёжность PWA** — [#50](https://github.com/Alexio00/HEALTH/issues/50) и [#58](https://github.com/Alexio00/HEALTH/issues/58) открыты; зелёный PR-контролируемый `static` не доказывает неизменность trusted scope policy.
- **Scheduler** — [#65](https://github.com/Alexio00/HEALTH/issues/65), [#82](https://github.com/Alexio00/HEALTH/issues/82), [#87](https://github.com/Alexio00/HEALTH/issues/87): нет согласованного cutover, trusted heartbeat и launcher-SHA release gate.
- **Вакцинации и схема** — [#41](https://github.com/Alexio00/HEALTH/issues/41), [#42](https://github.com/Alexio00/HEALTH/issues/42), [#62](https://github.com/Alexio00/HEALTH/issues/62): новые SQL-таблицы нельзя вводить отдельно от Writer/Verifier/Validation.
- **Финальная очистка** — [#57](https://github.com/Alexio00/HEALTH/issues/57): до завершения разработки не удалять старые ветки, истории, уникальные свидетельства и оригиналы.

**Состояние 13.10.2026:** владелец разрешил переход на каноническую базу Supabase и активировал ограниченный Writer. GitHub-документация описывает реализацию; фактическое состояние и полномочия подтверждаются **живыми приватными** HealthDB Project State / Project Manual и относящимися к конкретной операции проверками.

## Действующая реализация

- [Работа Writer](WRITER_OPERATOR.md), [политика Session pooler](WRITER_SESSION_POOLER_RUNTIME_POLICY.md), [журнал миграций](WRITER_MIGRATION_LEDGER.md).
- [Модель данных](DATA_MODEL.md), [безопасность](SECURITY.md), [восстановление Auth](AUTH_RECOVERY.md), [резервирование и восстановление](BACKUP_AND_RECOVERY.md).
- [Публичный снимок управляющих границ](PROJECT_MANUAL.md) и [архитектура](ARCHITECTURE.md). Снимки в репозитории не переопределяют приватные живые управляющие документы.
- Канонические SQL-миграции расположены в `supabase/migrations/`; агрегированные `db/migrations/` — старые снимки.

## Исторические документы: не инструкция к повторному запуску

`API.md`, `AI_WRITE_OPERATION_DESIGN.md`, `AI_WRITE_ACCEPTANCE_PLAN.md`, `AI_WRITE_AUDIT_CLARIFICATIONS.md`, `AI_WRITE_RULE_TRACEABILITY.md`, `WRITE_PATH_DECISION.md`, `POST_CUTOVER_AI_WRITE_PROTOCOL.md`, `WRITER_DELETION_PROTOCOL_CANDIDATE.md`, `WRITER_SOURCE_AUTHORIZATION_TEST_BOUNDARY.md`, `writer-resumable-test-acceptance-20261012.md` фиксируют прежние решения, кандидатов и тесты. Их старые значения `deferred`, `disabled`, `PASS` в синтетической среде не меняют текущее production-состояние и не разрешают клиническую запись.

Исправления/отмены в действующем Writer требуют точного кандидата с CAS, сохранения исходной идентичности REC/NNN и аудита прежнего состояния. Удаление производных данных типизировано и требует независимой проверки; физическое уничтожение REC или Source запрещено. Неоднозначные клинические последствия согласует владелец.

`MIGRATION*`, `FULL_MIGRATION_PLAN.md`, `MVP_*`, `WORK_ACCEPTANCE_20261011.md`, `PRODUCTION_ACCEPTANCE_RECONCILIATION.md`, `MISSING_CHECK_APPLICABILITY_20261011.md` — исторические отчёты/планы. Они **не** являются основанием повторно проводить или финализировать уже завершённую миграцию.

## Как трактовать результаты проверки

- PASS относится к конкретной операции, версии кода, входным данным и типу доказательств. Результат на синтетике не заменяет фактического чтения Source bytes, восстановления полного архива или проверки медицинского изменения.
- Правило 18 требует лабораторного контекста своей операции. Отказ владельца от ручного тестирования PWA — **не** выполненный тест.
- Одно принятое историческое исключение целой неизменённой строки по дате/ID **не** ослабляет проверку новых REC.
- Восстановление не возобновляет автоматически Writer и незавершённые загрузки.
- Старый проект, Registry/REC Docs и оригиналы сохраняются. Публичный GitHub не содержит медицинские строки, личные имена файлов, приватные локаторы провайдеров или секреты.
- Если в конкретном чате недоступен проверенный ограниченный оператор Writer, он остаётся **только для чтения**. Подключение внешнего ChatGPT-проекта требует установки владельцем актуальных приватных инструкций.

**Текущая разработка PWA:** выпуск идёт из ветки `pwa`, а не `main`. [Управление выпуском](https://github.com/Alexio00/HEALTH/blob/pwa/docs/PWA_RELEASE.md). Известное HIGH-ограничение независимости scope-check сохранено в [Issue #50](https://github.com/Alexio00/HEALTH/issues/50). Действующий `main` не менять без полного нового принятия Writer SHA.
