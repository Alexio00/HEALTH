# HEALTH — контракт совместимости Schema ↔ Writer ↔ Verifier ↔ Validation ↔ PWA (Issue #62)

**Статус: ARCHITECTURE DRAFT / техническое предложение 14.10.2026, не внедрено, не медицинская авторизация.**
Источники принятого поведения: приватные актуальные Project State/Manual; принят `HEALTH/main` **`3409791f1ffc5749020e7ff07139b0cec722f6fc`**; Issue #62; conceptual owner-approved model [#41](https://github.com/Alexio00/HEALTH/issues/41)/[Draft #45](https://github.com/Alexio00/HEALTH/pull/45). Ни один открытый Draft, CI или эта спецификация не меняет рабочую Supabase/Writer. Здесь нет реальных REC, Source locator, PII, данных или Secrets.

## 1. Строгое правило классификации

Для каждого PR, затрагивающего `supabase/migrations`, `db/migrations`, SQL reader, `scripts/writer/`, `frontend` или Writer API, автор до реализации классифицирует diff и указывает full BASE/HEAD SHA:

- `PWA_ONLY`: только существующее read-only отображение, без новой медицинской семантики или API/schema drift. Независимая приёмка `pwa`, `static`, browser postcheck.
- `READ_SCHEMA_ONLY`: view/index/read projection, при доказанном отсутствии изменения Writer row shape, grants/RLS/private evidence и trigger/constraints. При любом сомнении -> `UNDETERMINED`. Применение SQL требует отдельной технической процедуры, не фронтенд merge.
- `WRITER_IMPACT`: изменение любой клинически записываемой таблицы, столбца (включая nullable/default), типов, CHECK/FK/UNIQUE, writable status, trigger, owner intent/delta, checkpoint, verification/Validation/provenance, privilege/RPC. **Никакого независимого schema release**.
- `CONTROL_PLANE`: `main` SHA, signed GitHub OIDC, privileges, trusted workflow, release status/Secrets; отдельная security и owner exact-SHA приёмка.
- `OPERATIONS`: backup, restore, Source root, scheduler rotation и runner trust: отдельный operational gate.
- `UNDETERMINED`: fail closed для зависимой интеграции до архитектурной проверки.

## 2. Непосредственно проверенное несовпадение принятого кода

В принятом `scripts/writer/standby_runtime.sql`, `health_writer.check_changes` содержит закрытый перечень из 12 writable public tables и отвергает остальные. Для `INSERT` функция сверяет `pg_attribute` и требует **каждый физический столбец** в candidate row — даже nullable. `health_writer.propose` блокирует явный набор таблиц, вычисляет before/after checkpoint. В `scripts/writer/fixture_runtime.sql` (синтетический fixture, **не источник доказательства production-модулей**) `checkpoint()` сериализует перечень таблиц; `apply_delta_internal` имеет явный per-table ключевой dispatch. Все предложенные `vaccination_*` отсутствуют в этих перечнях.

**Следствие:** успешный `CREATE TABLE` и `SELECT` PWA не делают введённую дозу publishable или proof-bound. Нельзя просто дописать новые таблицы в allowlist и считать интеграцию завершённой; требуется точная связка delta, snapshot/locks, verifier, audit, Validation и permissions.

## 3. Версионированный концептуальный vaccination contract v2 (НЕ финальный SQL)

Owner-approved domain design от 13.10.2026:

| Предложенная сущность | Что представляет | Неизменный принцип |
|---|---|---|
| `vaccination_courses` | доказанный курс или сезон | отсутствие сведений не создавать искусственный курс |
| `vaccination_antigens` | канонический target/infection key | не выводить инфекцию только из похожего названия продукта |
| `vaccination_administrations` | **один фактический укол/введение** с доказанной датой и продуктом | один физический факт даже при N target, status pending/verified/retracted |
| `vaccination_administration_antigens` | связь введения с каждым конкретным антигеном | **индивидуальные** `stage_kind`/`dose_number`/`course_id` и provenance; не копировать этап A в B |
| `vaccination_evidence` | REC/source доказательство роли administered/prescribed/supporting для события или конкретного антигена | event-wide `antigen_key=NULL` не является автоматическим доказательством этапа каждой инфекции |
| `vaccination_plan_links` | доказанная связь `plan_item_id` ↔ `administration_id` + `antigen_key` | `fulfills` только для действительно совпавшей плановой инфекции/этапа, не по дате или одному продукту |

Одно введение комбинированного препарата — одна строка History; Latest by infection — по строке на подтверждённый антиген со ссылкой на ту же administration; Planned — отдельные доказанные обязательства. `Rv`, `Rv1`, `Rv2` — большая латинская R и маленькая v. `unknown` stage с номером запрещён. Разные сезонные курсы и повторные введения не схлопывать.

**SQL proposal #45 НЕ production-ready:** final version — **одна reviewed v2 migration**, а не исполнение v1 плюс четырёх ALTER-патчей последовательно. Владелец утвердил предметную концепцию, не схему/grants/публикацию, не разрешал клинический import. Нельзя использовать `basis_record_id` как доказательство назначения врача или `source_id` как доказательство связи REC без независимой проверки `record_sources`.

### Обязательные решения до фиксации SQL v2

1. `stage_source_text` является документальной цитатой уровня введения или antigen-specific доказательства; одно каноническое место для интерпретированного stage на antigen link, без двух меняющихся источников истины.
2. Event-wide `vaccination_evidence.antigen_key=NULL` и antigen-specific composite FK; уникальность с `NULLS NOT DISTINCT` — на целевом PostgreSQL, без дублирования roles.
3. `vaccination_plan_links.antigen_key NOT NULL`; composite FK `(administration_id,antigen_key)`; состав PK/уникальностей и proof, что `plan_items` действительно относится к указанной инфекции. Связь одного плана с другим антигеном не допускает `fulfills`.
4. `verified` требует настоящего `administered` REC evidence, actual date, >=1 независимый antigen link и достоверные references. Один SQL `CHECK(administered_on IS NOT NULL)` не обеспечивает доказательство.
5. `retracted` не означает физическое удаление. Изменение статуса обесценивает зависимые Latest, plan links и Validation до повторной проверки.
6. Связь `record_id` и `source_id`: оба должны независимо существовать, а Source доказательно принадлежать указанному REC/назначенному основанию (или отдельное owner-approved исключение).
7. Reader должен получать строго типизированный контракт, с явно обозначенными `unknown`, без infer от строк/просроченной даты. Никакого `INSERT/UPDATE/DELETE` в браузере.

## 4. Матрица технических изменений и участников

| Изменение | Изменить/проверить в Writer и Verifier | Validation/Reader | Готовность |
|---|---|---|---|
| 6 новых writable tables | `check_changes` allowlist, primary/composite keys, exact actions, deterministic full INSERT, `apply_delta_internal` и authorizer scope | каталоги/fixture, RLS/grants, UI joins | **NOT IMPLEMENTED** |
| Новые FK/columns/status | before/after/checkpoint, ordered locks, CAS, immutable identity, idempotent replay | stale evidence и integrity checks | **NOT TESTED** |
| Event/antigen evidence | кандидат, independent semantic + Source verifier, exact REC provenance и SHA receipts | pending/verified/retracted, без auto-clinical inference | **NOT TESTED** |
| Plan links | antigen-level proof/eligibility и связывание с активным plan status | completion/retract/reschedule и Validation dependencies | **NOT TESTED** |
| RLS/restricted SQL | запрет прямой записи, server RPC только bounded; scope role grants включая sequence/identity/defaults | `authenticated` owner reader SELECT only; `anon` denied | **NOT TESTED** |
| Публикация/откат | полный operation-bound snapshot/checkpoint, audit/validation, one SQL commit, COMMIT-UNKNOWN reconciliation, current writer exclusion | PWA старой и новой версии без повреждения клинического слоя | **NOT TESTED** |
| Release trust | owner-signed exact intent/candidate, accepted main SHA и broker/runtime identity; не использовать PR green как authorizer | независимый exact-SHA review, owner GO и readback | **NOT APPROVED** |

**Нюанс privilege:** `service_role` нельзя объявлять fail-closed только на основании `REVOKE` или RLS: Supabase `service_role` обладает специальными возможностями обхода RLS. Тесты должны проверить фактические `has_table_privilege`, роль исполнения RPC, owner/security-definer и deny для browser; service credentials никогда не выдаются браузеру или обычному Writer.

## 5. Требуемая матрица синтетических acceptance tests (только disposable PostgreSQL 17)

Минимум один positive и каждый negative ниже с сохранением точного до/после fingerprint:

| Probe | Условие | Ожидаемое |
|---|---|---|
| COMP-01 | старый Writer + новая таблица | явный unsupported clinical table; никаких изменений |
| COMP-02 | старая `plan_items` INSERT-форма после добавления nullable-колонки на disposable fixture | reject: explicit deterministic columns, отсутствие partial COMMIT |
| COMP-03 | нет `administered` evidence или дата неизвестна, status verified | reject; `pending` допустим только при валидной форме |
| COMP-04 | один комбинированный укол (synthetic targets A,B), известен stage только A | 1 History; Latest A со stage, B unknown; нельзя дублировать укол |
| COMP-05 | план на target A, ссылка / антиген B пытается выполнить план | reject; status plan unchanged |
| COMP-06 | event-wide Source/REC evidence без antigen-specific stage | никакого автоматического stage B |
| COMP-07 | неверная `record_sources` пара, только существующие по отдельности IDs | reject/require explicit verified independent evidence |
| COMP-08 | changed/retracted candidate после выдачи semantic receipt | прежний receipt invalid, CAS/stale before rejected |
| COMP-09 | concurrency Writer/backup + две операции / replay / lost COMMIT ACK | единый active writer; идемпотентность, UNKNOWN reconciliation, не двойное введение |
| COMP-10 | orphan/duplicate antigen, conflicting verified stage, invalid Rv number | fail FK/unique/check/verifier, state unchanged |
| COMP-11 | `anon`, outsider `authenticated`, authorized reader пытаются DML | все DML denied; owner SELECT только с `app_readers` |
| COMP-12 | old PWA reader после schema change; new reader с combined case | нет ложных значений, безопасный fallback/откат, no browser write |
| COMP-13 | старая таблица и отсутствие migration в новом Writer | Writer fail closed until accepted schema; никакого fallback SQL admin |
| COMP-14 | смена accepted `main` SHA, stale owner approval, changed candidate digest | no Writer publication despite CI PASS |

Сохранять анонимные фиктивные инъекции, не реальные имена препаратов, даты или медицинские Sources. Проверять реальные SQLSTATE, before/after rowsets, отказ role-grants, а не только текст unit assertions. Все эти probes сейчас **НЕ ЗАПУСКАЛИСЬ** и **не являются PASS**.

## 6. Порядок интеграции и роль каждого контура

1. Архитектор фиксирует v2 versioned schema/read/delta contract, открытые вопросы, diff-based impact map и угрозы. Issue #62 остаётся **OPEN**.
2. Writer developer проектирует точный bounded delta/Verifier/Validation/Source receipt для новых сущностей **отдельно от** текущих Gateway/Browser Consent candidates; не редактирует другие чаты и `main`.
3. PWA developer продолжает независимый UI-only #80/#85; legacy projection #59 не считать живой integrated table. Разрабатывает условный reader adapter/joins под согласованную версию, без размещения SQL DML в браузере.
4. Независимый security reviewer выполняет disposable PG17 tests, role/permission negatives, несовпадение схемы и stale receipts; подтверждает one migration и безопасную совместимость двух версий reader.
5. Предложение rollout: finalize one migration + bounded Writer code + verifier/Validation + reader контракт; принять согласованный exact `main` SHA, OIDC/broker/runtime и separate owner GO. Перед первым включением новой записи нужно проверить, что любые временно добавленные объекты не открыли browser DML и что прежний Writer по-прежнему безопасно обслуживается; при невозможности доказать непрерывную совместимость rollout остановить. Не создавать CLI/admin обход в production.
6. Только после реального migration/Writer acceptance и подтверждения PWA reader/Pages browser QA возможно выпускать интегрированный vaccination UI. Историческая сверка настоящих фактов из #42 — отдельное owner-authorized медицинское действие через принятый Writer, не техническая миграция.

**Rollback:** никакого автоматического DROP или purge после записи новых медицинских фактов. До записи — отдельно проверенный fail-closed rollback миграции/привилегий. После — forward fix с сохранением immutable facts, Source и audit/NNN, восстановление только по полному owner-approved disaster protocol (Writer disabled). Повторное принятие `main` обязательно даже для docs-only merge.

## 7. Definition of Done для Issue #62

Классификация отражена в релизных PR; утверждённая совместимая **final v2 migration** и schema/Writer matrix имеют точные версии; все 14 сценариев + additional adversarial negatives подтверждены независимым review в disposable PG17; Writer/Verifier/Validation/RLS/reader интеграция проверена end-to-end; owner утвердил exact technical release и отдельно любую clinical import; после релиза постпроверены production schema/code/reader без медицинских изменений. **Пока это предложение, а не закрытие Issue.**

## 8. Architecture decision candidate — verified against live schema metadata (14.10.2026)

**Scope verified read-only:** current `public` catalog metadata (table/column/PK/FK only, **no patient rows**) and accepted GitHub `main` SHA `3409791f1ffc5749020e7ff07139b0cec722f6fc`. This is architecture **design-ready for implementer review**, NOT an approved migration. Subsequent schema changes invalidate this snapshot.

**Current hard facts:**
- Canonical `public` has **zero `vaccination_*` tables**. Six-table draft #45 is therefore not deployed. There is no safe direct clinical writer path to these hypothetical objects.
- `public.plan_items(plan_item_id, title, status, due_on, basis_record_id, metadata, updated_at)` has no normalized antigen/target key and its `status` is `planned|done|cancelled`, **not** `fulfilled`. Draft `vaccination_plan_links.link_kind='fulfills'` must NOT be confused with or directly substitute for `plan_items.status='done'`.
- `public.record_sources` key is `(record_id,source_id,role)`; FK existence of independently valid `source_id` and `record_id` does not prove this pair. Event evidence needs the actual proven REC↔Source binding (or separately reviewed explicit exception).
- `health_writer.check_changes` on accepted `main`: **12-table closed allowlist**, rejects new vaccination tables; every INSERT must supply all physical columns including nullable ones. `health_writer.propose` uses its own fixed lock/table set; `fixture_runtime.sql` maintains a separate explicit checkpoint list and per-table key dispatch. These are **distinct lists and call sites**; updating any one is insufficient.

**Minimal v2 design contract to hand off:** retain owner-approved six conceptual entities (courses, antigens, administrations, administration-antigens, evidence, plan links). An administration is a real physical event; event-level source literal may be retained without becoming global interpreted stage. The **only interpreted stage of each target** belongs to the administration-antigen relation; missing course or stage stays NULL/unknown. An evidence row with `antigen_key=NULL` is evidence about the event, not proof of a per-antigen stage. Stage `Rv` is permitted with unnumbered booster; `Rv1`, `Rv2` use per-antigen numeric stage. Unknown must never inherit from a sibling antigen. Retraction is status transition, not REC/Source destruction.

**Plan integrity boundary — explicit implementation choice:** use the six-table model **only if** independent Writer/Verifier attestation can prove the relevant `plan_items` item targets the *same antigen and required stage*, with precise REC/source evidence recorded in an operation-bound immutable receipt. A composite FK `(administration_id,antigen_key)` proves the antigen belongs to that administration, **not** that the `plan_item_id` is about that antigen. On ambiguous plan target: allow no `fulfills` link, do not change `plan_items.status`; keep unresolved as a question or `related` with correct provenance. If durable per-plan target cannot be proven without inferred metadata, **STOP** and return for an owner-reviewed schema extension (e.g. normalized plan-target relation); do not silently introduce an extra table or populate guessed values. A `fulfills` link does not itself perform a plan status update; any `done` transition is an independently authorized, independently verified delta.

**Required integration acceptance — no single-layer shortcuts:**
1. Freeze one versioned final v2 schema and stable PWA reader contract; test against disposable PG17 and real accepted schema metadata. Do **not** execute v1 + draft ALTER fragments as production migrations.
2. Writer owner-intent/delta semantics, explicit full INSERT shape, exact composite keys, immutable event identity, stale CAS, before/after snapshot/lock/checkpoint, authorization and audit must cover all writable new objects in a coordinated technical release.
3. Independent Verifier must establish an actually administered REC, date, antigen-specific facts and source/record binding; avoid promoted `verified` on recommendation/prescription alone. Validation must include proposed tables and invalidate stale receipts on corrections, retractions and plan changes. If verified dates/stages absent, fail closed or retain appropriately limited `pending` state.
4. On exposed tables enable RLS; separately verify explicit browser `authenticated` SELECT is conditioned on `app_readers`, `anon` has no access, all browser DML is rejected, public functions/sequence grants cannot bypass controls. RLS alone does NOT constrain a privileged `service_role`; test actual grants and SECURITY DEFINER boundaries.
5. The rollout is **not an ordinary PWA deployment**: freeze/disable impacted clinical publication, obtain bounded backup/recovery evidence, apply one coordinated schema+Writer+Verifier+Validation change, independently verify exact accepted `main` SHA and signed broker/runtime pin, then enable reader only after grants and API contract readback. Do not let old Writer write a half-upgraded schema. Before clinical rows, revert safely only through a reviewed rollback; after clinical rows, preserve facts and prefer reviewed forward repair or formal recovery. Separate owner GO for any historical medical import (#42).
6. All schema-affecting PRs must carry a table-level `schema change -> Writer impact -> verifier/Validation -> reader/RLS -> synthetic test/evidence` matrix and compare to their **current** BASE/HEAD, not to this frozen 14.10 snapshot.

**Implementation review blockers, not owner-approved new features:** no proven normalized plan target in current table, final evidence-null semantics/uniqueness not tested, stage provenance scope, source binding/role grants untested, Writer/Verifier/Validation/reader not integrated, no independent end-to-end disposable PG17 run. Issue #62 stays OPEN; this document alone is not sufficient to grant technical or clinical release.

## 9. A62-C1 — corrective architecture contract after independent FAIL

**Provenance:** independent audit 14.10.2026, exact prior #83 HEAD `17cc624a1b4f7deeab2c00c34cfbaf2f34f7a148`: **ARCHITECTURE_CONTRACT_FAIL / 2 BLOCKER, 5 HIGH, 2 MEDIUM**. This section is the proposed **single bounded correction**, not an accepted production implementation. All nine findings (A62-01…09) remain subject to targeted independent re-review. Six conceptual tables retained. Do not release fragments from Draft #45.

### 9.1. Typed private plan attestation and ALL-obligation predicate — A62-01 BLOCKER

One `plan_items` row is a plan obligation container, **not a single antigen by implication**. Before any `vaccination_plan_links.link_kind='fulfills'`, the independent verifier must issue an immutable, versioned, operation-bound **PLAN_FULFILLMENT_CLAIM_V1** in the existing *private* Writer proof/audit channel, never via browser/ChatGPT asserted text. Minimal typed fields (names are normative conceptual data-contract keys, exact serialization must be frozen with the implementation):
- `claim_version`, `schema_version`, `writer_accepted_sha_at_issue`, `operation_id`, `request_key`, `intent_sha`, `candidate_sha`, `expected_before_sha`, `expected_after_sha`, `verifier_principal`, `issued_at`, `claim_digest`;
- `plan_item_id`, **full canonical `plan_row_sha`**, separately verified prescribed/recommended REC and source proof, explicit immutable `obligations[]`. Each obligation has a stable within-plan key, **canonical antigen_key**, required course/season, required stage-kind and numbered/un-numbered policy, and any minimum age/time/date constraints actually proven. Absent or ambiguous values are `unknown`, not guessed;
- `matches[]`: for **each obligation** exact `administration_id`, `antigen_key`, stage/course, **full row hashes** of administration, membership, course if applicable, evidence, REC, `record_sources` and Source proof, plus semantic conclusion `PASS`/failure with rationale. A foreign key proves existence, never clinical meaning;
- `complete = true` only iff the **complete set of required plan obligations is known and every obligation independently matches an active verified administered antigen** at the required course/stage; a single fulfilled antigen of a multivalent vaccine cannot automatically close a multi-target plan. For partially satisfied or unknown plans no `fulfills` link and no derived `done`; a proven `related` link is allowed without implying completion.
- A `fulfills` link references `proof_operation_id` and opaque `proof_sha`, but these fields alone do not assert validity. The verifier independently compares them with the private exact typed claim. A separate owner-approved Writer delta must change `plan_items.status` to `done` if warranted; a link cannot update the plan implicitly.

The plan title or free-form metadata is not a reliable target oracle. If an existing plan item cannot be converted into an independently verifiable complete typed obligations set, **deny fulfills/done** and request exact owner clarification. Do not introduce a seventh table merely as a substitute for source/semantic proof.

### 9.2. Current validity, dependency closures and correction — A62-02 BLOCKER

`proof_is_current(plan, claim, database, accepted_policy)` is TRUE only if: immutable claim digest and issuer are valid; the issuing Writer SHA/schema/claim version is in the **explicitly accepted compatibility set** (do **not** require equality to the latest docs-only main SHA); full current hashes match *every recorded dependency*; event status is `verified`, not `pending`/`retracted`; all membership/stage/course and administered evidence semantic checks remain true; all plan obligations remain met; no correction/supersession/cancellation invalidates that proof. Historical receipts are preserved but must not be returned as **current** after a dependency changes.

Any owner-authorized operation that changes/retracts administration, date, stage, course, membership, evidence, REC, `record_sources`, Source claim or plan obligation must enumerate affected dependent links and plan rows, recompute the typed proof **under the same Writer lock/checkpoint** and atomically perform one of:
1. replace proof and retain `fulfills` + `done` when an independently verified alternate current satisfaction exists;
2. downgrade/delete invalid `fulfills`, and, when the plan's `done` was derived from that claim, transition to `planned` or `cancelled` only with the exact **new owner-approved** plan delta;
3. **reject the entire operation before COMMIT** if plan status/owner decision cannot safely be reconciled.

Do not rewrite a manually owner-completed plan without proving its origin; instead BLOCK for owner clarification. No temporary committed `retracted + fulfills + done`. CAS, before/after snapshot, all dependent table locks and Validation must cover the same transaction. Reader current-state projections must exclude historical claims on failure and preserve their audit provenance privately.

### 9.3. Independent fact vs membership vs stage — A62-03/A62-04 HIGH

- `verified` administration means **actual physical administration**, independently demonstrated with dated `administered` REC evidence. The event must have at least one proven antigen, and **every membership published for a verified event** must have its own independently supported antigen target. If A is proven and B conjectured, B MUST NOT appear in verified latest/current memberships; retain uncertainty privately as pending/question, not as a verified B.
- An observed/proven antigen with unknown dose order may have `stage_kind='unknown',dose_number=NULL` and still be a proven administration. `stage_kind='dose'` MUST have a positive explicit number; `revaccination,NULL` renders `Rv`; `revaccination,n` renders `RvN`. Never infer B's stage from A or infer vaccination from a recommendation, preliminary appointment or planned date.
- Evidence claim scopes: `antigen_key=NULL` is **event-only** and **cannot alone certify any target membership or its stage**. An antigen-specific claim must reference the real composite membership. A source claim identifies `record_id,source_id,source_role` matching `record_sources`, exact source-byte verification and the literal clinical fields covered; `source_id=NULL` is permitted only with explicitly attested owner statement/not-applicable provenance, never an implicit bypass. The independent semantic reviewer, not FK or `evidence_role` text alone, decides administered vs prescribed vs supporting evidence.
- If later evidence alters a proven target/stage, treat it as the dependency invalidation in §9.2.

### 9.4. Writer/Validation exact implementation interface — A62-05 HIGH

Before implementing any new data operation, freeze one `VACCINATION_DELTA_V2` row contract per table: exact primary/composite key; INSERT/UPDATE/DELETE permitted transitions; **all physical INSERT columns including nullable ones**; deterministic UUID for `evidence_id` supplied *before* proposal (do not rely on identity nextval or clock defaults); immutable provenance and correction mechanism; canonical JSON serialization/order and digest. Plan rows and SOURCE rows retain their existing published identities. `vaccination_antigens` is a controlled dictionary: modifications require separately reviewed technical owner intent, not arbitrary user-submitted clinical deltas.

Update as a single integration unit: `health_writer.check_changes` 12-table allowlist; `apply_delta_internal` composite-key dispatch; candidate/projection, both proposal and finalize snapshot/checkpoint/locking paths; Verifier Source and semantic receipts; typed PLAN_FULFILLMENT_CLAIM_V1 checks; Validation registry and dependency invalidation (existing 37 check names are **not** vaccination acceptance); RLS/ACL/function and sequence grants; versioned private clinical reader API. Reject old Writer/new schema as well as new Writer/old schema; no partial release.

### 9.5. Versioned Reader API and safe fallback — A62-08 HIGH

Reader `VaccinationReadV2` must be a **server-derived, read-only**, versioned DTO: event `administration_id, administered_on, product_name, verification_status`; target `antigen_key, stage_kind, dose_number, stage_label, membership_verified, current_proof_valid`; plan `plan_item_id, obligations_complete, fulfillment_current`; provenance limited to safe record IDs/labels (no private proof payload or Source physical locator). History shows verified current facts as such, separately labels historical/retracted/pending; per-antigen Latest includes **only** verified currently proven memberships; Planned must use the exact current plan/claim status and never infer completion from text. A missing/unsupported DTO version must **fail closed for canonical claims** rather than let legacy REC/plan heuristics resurrect retracted events. Existing #59 is legacy projection, not canonical graph integration; #80/#85 remain independent UI scope.

### 9.6. Release and rollback gates — A62-06/A62-07/A62-09 and cross-component

- One consolidated reviewed six-table schema **draft** must replace the historic sequential v1→stage→relations→keys SQL path. The observed SQLSTATE **42704** was caused by dropping the same index after its `course_id` column was already removed; this is not a successful migration. `dose,NULL` is rejected by the final stage CHECK, while `Rv,NULL` is permitted.
- Gate entry: confirmed Writer publication disabled and pending requests reconciled; independently verified usable backup/full restore route and synthetic before-state; accepted versions of schema, Writer, Verifier, Validation and reader prepared. Failure at any stage leaves clinical publication disabled.
- Gate exit: one transactional DDL, actual PG17 disposable positive/negative tests, grants/RLS readback, exact authorizer/broker and runtime pin reacceptance, independent SHA review and separate owner GO; only then enable Writer and dependent V2 reader. No migration/import authority follows from this proposal.
- Rollback **before first new clinical row**: reviewed reversal of schema/code/grants/pin with proof no records lost; **after first new clinical row**: reviewed forward repair or separately owner-approved full recovery, no destructive drop of new clinical evidence. Rolling back PWA must not resurrect legacy heuristic claims as current.
- Draft #45 historically exposed a private document locator. It must be removed from the current public HEAD and history/caches/forks separately assessed with an **explicit owner disposition**. Never reproduce the private URL/ID in public evidence. Fixing HEAD does not erase Git history.

**Acceptance tests proposed, not RUN here:** all A62-01…09 negative scenarios from the independent report; multi-antigen partial plan, unknown membership vs unknown stage, wrong REC/Source pair, no administered evidence, retraction with stale `done`, date/stage/plan/Source correction, old/new Writer-schema mismatch, nullable INSERT, deterministic UUID, duplicate/null evidence, strict stage CHECK, 54 role/table/action DML denies, Reader legacy-fallback rejection, concurrency/replay/UNKNOWN, and exact-SHA/rollback. The independent auditor's prior 34/34 bounded slice and 9/9 supplemental probes do **not** constitute vaccination E2E or a full Writer-suite PASS.
