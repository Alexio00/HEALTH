# HEALTH Writer / ChatGPT Gateway — состояние разработки

**Срез на:** 2026-10-17  
**Назначение:** технический журнал состояния разработки и локальных аудиторских пакетов.  
**Статус:** локальные компоненты частично приняты; архитектурный Gate 2 ожидает решения Product Owner; полноценный ChatGPT Writer Gateway не интегрирован; production daily use — **NO-GO**.

> Этот документ фиксирует состояние и доказательства. Он не заменяет приватные `HealthDB — Project State` / `HealthDB — Project Manual`, не принимает архитектурный риск от имени владельца и не разрешает SQL, Auth/Edge provisioning, merge, deployment или медицинские записи.

## 1. Управляющая граница и текущие GitHub refs

| Объект | Проверенное значение |
|---|---|
| Репозиторий | `Alexio00/HEALTH` |
| Принятый `main` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` |
| Наблюдавшийся `writer-code` HEAD | `7d67ae96b8f8e344321a4df87e467fff71a20652` |
| Draft PR #84 | HEAD `646625fbf9da62628d82386bde1c2987be45cd10`, branch `fix/writer-gateway-readiness-semantics-20261014`, base ref `writer-code` |
| Draft PR #35 | HEAD `bda786d72db54e08b9da949dcce3c9d54eb2a5b9`, branch `feature/chat-writer-contract-20261013`, base ref `writer-code` |
| Issue #34 | ChatGPT Writer gateway: авторизованный интерфейс записи без доступа модели к секретам |
| Issue #74 | Следующая итерация: ошибки до исходного чата, проверка статуса и технический handoff |

PR: [#84](https://github.com/Alexio00/HEALTH/pull/84) · [#35](https://github.com/Alexio00/HEALTH/pull/35) · Issue [#34](https://github.com/Alexio00/HEALTH/issues/34) · Issue [#74](https://github.com/Alexio00/HEALTH/issues/74).

### Важное замечание о refs

В GitHub API-снимке от 2026-10-17 PR #35 и #84 указывают `base.ref=writer-code`, но `base.sha=3409791f1ffc5749020e7ff07139b0cec722f6fc`, тогда как отдельный запрос ветки показывает `writer-code` HEAD `7d67ae96b8f8e344321a4df87e467fff71a20652`. Это несогласованность наблюдаемых ответов/снимков; она **не** разрешена предположением. Повторно сверить refs и точные SHA перед любым merge, reacceptance или release.

Последний известный снимок приватных управляющих документов: `HealthDB — Project State` и `HealthDB — Project Manual` `18, modified 2026-10-14. В этой сессии live-read Drive не был доступен, поэтому перед любым release-действием их необходимо перечитать и сверить с текущим состоянием. Этот статусный документ не изменяет управляющие источники.

## 2. Хронология локальных пакетов и независимой приёмки

Все перечисленные ZIP — локальные synthetic/evidence-пакеты, а не merged GitHub PR и не deployed-компоненты. Их SHA-256 в таблице проверены по фактическим локальным файлам на момент подготовки этой записи.

| Этап / артефакт | SHA-256 ZIP | Результат независимой проверки | Что это означает — и чего не означает |
|---|---|---|---|
| Stage-qualified journal A′ R1 | `d14219b73bde8a414779e7295099c34ee52f4dddeec72cae029b3a46a1b056b0` | PASS: структура, RLS/ACL, сохранение evidence и non-empty guards на PostgreSQL 17.11 | Локальная схема проверена; не развёрнута и не подключена к production Writer. |
| Stage CAS Local R0 | `1e92a32cfcf746501b435c541b57fa0659233920a78c4ff98bea38aeee7243b0` | PASS: DDL/stages/concurrency/TTL/rollback/ACL-RLS/evidence; 400 синхронизированных двухсессионных race и 538 negative cases | Только синтетическая приёмка компонентов. Signed intent verifier, trusted intent review, браузерная Auth и Writer integration не реализованы. |
| Intent Review Composer R0 | `6b247a000035230b87bb8f48d00e1950f184caecb9f2f55f9ed6192bc663ec12` | FAIL: 3 REQUIRED — небезопасная копия байтов, malformed UTF-16, неоднозначные Unicode separators/controls | Исходный дефект зафиксирован; R0 не принят. |
| Intent Review Composer REQUIRED R1 | `51ed044d3387d07e73521117438a35f337835b485ef18117a112546bcb0ddb36` | PASS: те же 13 контрпримеров R0 FAIL → R1 PASS; 59 авторских, 70 независимых, 30 дополнительных тестов; 228 Unicode-проверок | Принят локальный display-only composer с `authorized:false`; original-message provenance и trusted Reader integration не установлены. |
| Session Preview REQUIRED R1 | `97dfd28fbeb36319a97adc938bee01de8100684cc30fdfb48223bc570f874b7c` | PASS: 7/7 целевых регрессий; 135/135 независимых; 54/54 авторских; 22/22 дополнительных тестов | Байты сообщения фиксируются до async-границы, TTL проверяется перед Reader. Это локальный компонент, не реальная Auth/SQL/HTTP интеграция. |
| SQL Identity Proof Local R0 | `65864da5b9a08b84ce983d9f6071a6517b8a28406ce59ea075f30b2f91412c5a` | Исходный launcher имел 2 stdin regressions | R0 оставлен как parent для корректирующего delta. |
| SQL Identity Proof REQUIRED R1 | `4e80b090175f83700e2eaf55f87a76833ade0f8e280e5cb0c0686d2ad8d54995` | PASS: обе регрессии исправлены; 13 static/transport tests; неизменённый entrypoint реально выполнен на изолированном PostgreSQL 17.11 и вернул `LOCAL_SYNTHETIC_PASS` | Доказывает ограниченный SQL-role/launcher сценарий. Полная accepted Writer identity/ACL/TTL matrix заново не запускалась; deployable owner-to-SQL mapping не установлен. |
| Identity Bridge Design R0 | `4ec981db13ffbb2e05d8f8a474df44bfc5f2e7f87f36ee30a80c130d735e037a` | Parent архитектурного delta | Не является принятым решением C1/C2. |
| Identity Bridge Design REQUIRED R1 | `cea182f37eea62c3f0a6ee5df188f71363497409161ed8c08785773e742c43d8` | PASS: `IDENTITY_BRIDGE_DESIGN_REQUIRED_01`; восемь design delta-критериев; 17/17 статических тестов | Документальное исправление принято; `GATE2_ARCHITECTURE_REVIEW=NEEDS_OWNER_DECISION`. Вся planned runtime matrix из 30 SQL/Auth/flow cases остаётся `NOT_RUN`. |
| Gate 2 owner-decision brief | `99d6c5146e6975e20d6bf98521861aceb18a47c28080824ee830637c99045f87` (Markdown file) | Локальный briefing | Рекомендация исследовать O2 — не решение владельца и не разрешение реализации. |

### Дополнительные source bindings, проверенные на принятом `main`

- `scripts/writer/chat_worker.py` blob: `d48e4a0ebde2d5829817fbf0c3a1366b98abc0a8`.
- `.github/workflows/writer-authorization.yml` blob: `37fb22efb7fc1762e41fe3212600e61577e01d30`.
- `scripts/writer/standby_runtime.sql` blob: `b3e12e17435381029d69bdfaf3861280d0ef9bb7`.
- `scripts/writer/build_standby.py` blob: `cd6ac6b3d037ed1843a625e480fb1b1e462b9dcb`.
- `scripts/writer/durable_runtime.sql` blob: `3d6c105f962d7124e703f2098da39ed0eeab1b2e`.

Это привязки прочитанного исходного кода, а не утверждение, что локальные Preview/Identity пакеты интегрированы с ним. Reader R1 source hash в SQL Identity audit: `ba5cd5684d7c6c556997bbbda0f280d4afc21c2dcd1d42c5434d4863d044080c`; он также не доказывает deployable mapping.

## 3. Текущее архитектурное состояние

### Уже подтверждено локально

- Stage-qualified journal и CAS-механика прошли заявленные синтетические структурные, concurrency, TTL, rollback и ACL/RLS проверки.
- Intent Review Composer исправлен и независимо принят как **неавторизующий display-only** компонент.
- Session Preview исправлен и независимо принят в своём ограниченном локальном тестовом контракте.
- SQL Identity launcher корректно передаёт stdin и выполняется на свежем disposable PostgreSQL 17.11; ограниченный запрет `SET ROLE` воспроизведён.
- Identity Bridge Design R1 корректно описывает границы доверия, публичность `request_key`, риск stolen credential, необходимость live Auth checks и stop-before-approval.

### Не реализовано / не доказано

- `OWNER_SESSION_BINDING=NOT_IMPLEMENTED`.
- `TRUSTED_WRITER_PREAPPROVAL_READER=NOT_IMPLEMENTED` как интегрированный доверенный runtime reader.
- `ORIGINAL_MESSAGE_PROVENANCE=NOT_ESTABLISHED`.
- `DEPLOYABLE_SQL_IDENTITY_MAPPING=NOT_ESTABLISHED`.
- `BROWSER_AUTH=NOT_RUN`; live Auth revocation/session tests не проводились.
- `SIGNED_INTENT_VERIFIER=NOT_IMPLEMENTED`; `SIGNED_OWNER_ISSUER=NOT_IMPLEMENTED`.
- `EDGE_TCB_AND_CREDENTIAL_RISK=NEEDS_OWNER_DECISION`; least privilege отдельного SQL LOGIN не доказывает изоляцию всего Edge runtime.
- `WRITER_INTEGRATION=NOT_ESTABLISHED`.
- `PRODUCTION_DAILY_USE=NO-GO`.

Текущий принятый Writer связывает intent с SQL `session_user`. Отдельный Preview LOGIN, ограниченный `INHERIT FALSE, SET FALSE`, не получает права читать intent другого caller. Общий Writer LOGIN, напротив, сохраняет избыточные mutating capabilities. Локальный SQL Identity Proof не разрешил эту привязку.

В существующем `chat_worker` последовательность `submit → approve → prepare` не имеет требуемой паузы до authorization. Будущий Preview flow должен остановиться после durable submit и до authorize/prepare; просмотр не должен подтверждать медицинскую операцию.

`request_key` является публичным opaque correlation ID, а не bearer secret и не read authority. C1 допускает чтение pending intent при сочетании похищенного Preview credential и известного ключа. C2/эквивалентное DB-enforced read authority не реализованы; даже C2 не считается защитой от компрометации всего Edge TCB без отдельной изоляции signer/runtime.

## 4. Gate 2 — решение владельца остаётся открытым

Архитектурные варианты, перечисленные в локальном design packet:

- **O1 / C1:** принять Edge целиком как доверенную границу, включая остаточный риск похищенного Preview credential.
- **O2 / C2:** спроектировать независимое право чтения, привязанное к владельцу/сессии/запросу, и отдельно проверить signer/runtime isolation.
- **O3:** приостановить браузерный Preview до разрешения риска.

**O1/O2/O3 не выбраны.** Рекомендация сначала исследовать O2 — предложение для обсуждения, а не OWNER_GO. Ни C1 риск, ни C2 реализация не приняты. Создание новой таблицы/сервиса заранее не предрешено.

## 5. Следующие этапы и критерии перехода

1. **Решение Product Owner:** выбрать O1/O2/O3. Без него не начинать implementation Gate 2.
2. **Если выбран O2 — только design/review:** определить доверенный issuer и независимое право чтения, threat model stolen credential/ambient Edge secrets, lifecycle/expiry/revocation, replay/consume, границу исходного сообщения. Провести независимый design review до SQL/Edge implementation.
3. **Owner session binding и consent:** зафиксировать source/provenance точного текста; отделить authenticated identity от explicit consent; проверять verified non-empty session ID и актуальность сессии перед SQL и повторно перед outbound disclosure.
4. **Bounded Reader и SQL mapping:** доказать фактические principal/role/grants, отсутствие лишнего Data API/RLS доступа, pending-state/race semantics и TTL на реальном изолированном PostgreSQL; не считать prior R0 matrix новым R1 evidence.
5. **Orchestration:** реализовать stop-before-approval; чтение Preview не должно вызывать `approve`, `prepare` или публикацию.
6. **Независимая приёмка:** исполнить все planned SQL/Auth/flow cases, browser/Auth revocation и отрицательные сценарии на точном SHA. Разделять local synthetic PASS, hosted runtime PASS и production acceptance.
7. **Только после отдельных разрешений:** PR review, exact-SHA acceptance, явный OWNER_GO, повторная проверка перед merge и предусмотренная эксплуатационная приёмка. Успешный CI сам по себе не означает production GO.

## 6. Изменения и ограничения этой записи

- Этот статус создаётся отдельной документационной веткой от наблюдавшегося `writer-code` SHA `7d67ae96b8f8e344321a4df87e467fff71a20652`.
- Предполагаемый путь документа: `docs/WRITER_CHATGPT_GATEWAY_DEVELOPMENT_STATUS_20261017.md`.
- Целевой PR — Draft в `writer-code`; merge не выполняется.
- Эта запись не изменяет Writer SQL, Supabase/Auth/Edge, Secrets, GitHub workflows, медицинские записи или production.
- ZIP evidence остаются локальными пакетами; в GitHub записываются только технические статусы и SHA-256, а не приватные журналы/содержимое медицинских источников.
- Перед merge необходимо повторно прочитать актуальные Project State/Manual, перепроверить `main`, `writer-code`, PR bases и exact SHA. Текущая запись не является release approval.
