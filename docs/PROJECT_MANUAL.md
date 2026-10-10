# Project Manual

## Modes

- **read-only** — inspect, search, compare, validate.
- **maintenance** — change code, schema, automation, metadata, validation or technical state.
- **import** — copy or modify real medical data only under explicit owner authorization.

## Public-repository rule

Real medical data, source files, private filenames, provider file IDs/URLs, account identifiers, passwords, tokens, private keys and production `.env` values are forbidden.

Use synthetic fixtures for tests.

## Write model

Medical writes must use one logical operation:

`PREPARED -> COMMITTED_REGISTRY -> VALIDATED -> FINALIZED`

Interrupted work becomes `FAILED`.

The database must enforce a single unfinished mutating operation.

### Prepared design and acceptance documentation (no implementation)

- [AI_WRITE_OPERATION_DESIGN.md](AI_WRITE_OPERATION_DESIGN.md): normative future routine write states, atomic publication and fail-closed recovery, separate from the full-migration executor.
- [AI_WRITE_RULE_TRACEABILITY.md](AI_WRITE_RULE_TRACEABILITY.md): complete mapping of 37 active Drive-native Validation check names to PostgreSQL/semantic/legacy-only obligations, without copying medical details.
- [AI_WRITE_ACCEPTANCE_PLAN.md](AI_WRITE_ACCEPTANCE_PLAN.md): synthetic fixtures, adverse acceptance scenarios, evidence format and independent review gates. Documentation PASS is not a production write-path PASS.
- Health API, restricted PostgreSQL RPC and generic connectors are **not implemented or authorized** by these documents. No routine writes to new HEALTH until an independently accepted bounded writer and explicit owner cutover.

### Current writer and deferred post-cutover choices (owner decision 2026-10-10)

- The Drive-native HealthDB is still canonical. For now, **medical changes remain owner-authorized ChatGPT/AI actions through the active Google Drive tools** and follow the current Drive HealthDB Project Manual/State. The old Google Sheets Change Log/ID Reservations protocol is not replaced by this public HEALTH manual.
- New HEALTH accepts no routine AI medical writes before a separate owner cutover decision and accepted write-path tests. A migration runner is not a routine writer.
- A dedicated Health API and a restricted PostgreSQL RPC/stored-procedure alternative are both **deferred possibilities and are NOT under development**. Neither is mandatory by name; the eventual backend must enforce equivalent guarantees. See [write-path decision](WRITE_PATH_DECISION.md).
- SQL schema already creates `operations_single_writer_idx` to reject competing *active operation rows*. It does **not** automatically block privileged medical DML outside `operations`. Future roles/entrypoints must enforce this boundary; do not mistake an unrestricted SQL connector for an accepted write workflow.
- Medical meaning, provenance, exact Labs literals, OPEN/CLOSES owner decisions, immutable REC IDs and unused retired IDs survive cutover. Google Sheets ranges, Google Docs volumes and Drive logical-transaction steps do not become SQL procedures verbatim.


## Provenance

Do not invent missing data. Empty, absent and explicitly negative values are different states.

For laboratory observations, preserve literal source value, precision, units, reference range and source flag.

## Source abstraction

Canonical source identity consists of `source_id` plus `logical_path`. Physical storage belongs in source-location rows.

## MVP gate

Full migration is forbidden before owner approval of a working vertical slice with:
- representative records
- source opening
- laboratory data
- case links
- authentication/RLS
- backup/restore test
- old-to-new comparison
- latency and validation report

## Cutover

The legacy/current health database stays authoritative until the owner explicitly approves cutover.


## PWA table and navigation conventions

- Every table shown on GitHub Pages must support sorting by clicking the column title.
- Column headers use a neutral bidirectional sort marker by default and show ascending/descending direction when active.
- Do not render a separate text-filter row under table headers.
- Add a compact filter block before a table or card collection when the dataset has useful categorical/repeating values or a meaningful date range.
- Repeating categorical values should use select controls populated from the live dataset; filters are empty/All by default.
- The Records index always provides date-from/date-to and tag filters, and additionally exposes repeated Record Type / Confirmation values when more than one value exists.
- Tags in the Records table and REC page are interactive filter controls; selecting a tag immediately opens/updates the Records index with that tag active.
- Current State questions use the same collapsible-detail reading pattern as chronic states and open cases.
- Sources linked from a REC should open the original primary Google Drive object directly when a primary locator exists.
- Technical provenance fields such as link role and source hashes stay in the database/validation layer unless the owner explicitly asks to inspect them.
- These are presentation rules only; they must not weaken read-only browser access or embed medical data in the public repository.

## Frontend, visit preparation and medication intake (pre-full-migration)

- Current State is a composite view. The ten top-level pages are: Текущее состояние;
  Хронические состояния; Открытые случаи; Принимаемые препараты; Мониторинг;
  Подготовка к визиту; Будущий план; Закрытые случаи; Записи; Вакцинация.
  Vaccination remains empty until owner-supplied data exists.
- On mobile, navigation is closed by default and opened with an accessible hamburger
  toggle. On desktop, navigation stays in the header.
- Visit Preparation uses plan_items as the canonical planned-visit source and
  questions as the canonical question source. A question can appear for multiple
  explicitly named specialists without creating duplicate rows.
- Medical-card questions are exclusively internal contradictions, unresolved
  chart maintenance or actions to perform on the medical chart. Use question
  metadata.category=medical_card; pre-existing specialist questions belong to
  visit preparation, never to this category.
- Never infer a specialist or a visit date from unrelated clinical facts. If the
  question wording does not clearly name a specialist or there is no matching
  plan item, show that uncertainty explicitly rather than inventing one.
- New active medication intake MUST create exactly one open medical-card question:
  "Проверить лекарственные взаимодействия препарата «{name}» с другими
  принимаемыми препаратами", linked to the exact prescribing REC. Create it
  in the same controlled logical write as the medication and make it idempotent, regardless of whether the future implementation uses a Health API or restricted PostgreSQL RPC.
  If the prescribing REC is ambiguous, do not invent a link; defer/flag the
  intake for owner resolution. A question is a pending check, not a completed
  drug-interaction assessment. Existing-medication bulk migration is not new
  intake and MUST NOT automatically create these questions.
- The PWA is currently read-only. Before **post-cutover** production medication
  writes, an accepted controlled server-side write path must enforce that
  transaction-linked interaction-check question. Health API and PostgreSQL RPC
  are currently deferred alternatives; a prompt-only instruction does not
  enforce the rule. The existing Drive-native writer stays governed by the
  active Drive Manual until cutover.
- Preserve medical REC body_text exactly. Format for reading at presentation time
  (paragraphs, headings, lists, tables); formatting is not a medical rewrite.
- Display automatically recorded conversational/operational timestamps in
  Europe/Moscow (MSK, UTC+3), while storing PostgreSQL timestamptz as UTC
  instants. Preserve source document dates/times and their known original zone;
  never pretend an unknown source time zone is MSK.
- REC-YYYYMMDD-NNN and used/retired ID Reservations remain stable clinical
  references. PostgreSQL-generated numeric IDs for subordinate entities are
  technical identities only, not substitutes for REC provenance. SHA-256 verifies
  source bytes, not record identity.
