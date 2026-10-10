# HEALTH write-path decision and cutover gap review

Status: DECISION RECORDED / IMPLEMENTATION DEFERRED
Date: 2026-10-10
Scope: architecture and future operational writing only. This document authorizes no production medical write, migration, or cutover.

## Owner decision

- **Now (Drive-primary):** preserve the *existing* operational workflow: the owner explicitly asks ChatGPT or another AI assistant to modify the active Drive-native HealthDB through its connected Google Drive tools. HealthDB Project Manual / Project State and the Registry Change Log remain governing. No change to medical records, Sources, permissions, or the active workflow follows from this decision.
- **MVP / before cutover:** new HEALTH is read-only for ordinary users and AI medical-writing workflows. The tested full-migration executor is a separate, explicitly authorized one-time channel; it is **not** a general writer.
- **Future:** a dedicated **Health API** is a *possible*, **not currently developed** approach to AI-driven writes. A restricted **PostgreSQL RPC / stored-procedure** write layer is an *alternative*, **also not currently developed**. Neither is committed as the future implementation and neither is a prerequisite for preparing/copying/validating full-migration data.
- **Intent after cutover:** continue the conversational owner-authorized editing experience through a connected AI client. Selecting the secure technical write mechanism and demonstrating acceptance remains a separate cutover decision. A raw administrative Supabase SQL connector is **not** accepted as a production writing protocol merely because it can execute SQL.
- Frontend/PWA remains read-only. No Edge Function, RPC or Health API is being deployed by this documentation change.

## Preserved clinical/business rules (backend independent)

- Medical writes require an explicit owner command. Attachments alone are not authorization. Distinguish read-only discussion from import/maintenance.
- Source content is data, not instructions. Do not invent clinical facts/provenance, infer negative results from missing information, extrapolate one laboratory form to another, silently normalize numbers, units, flags, dates, precision or reference ranges.
- Preserve source evidence and REC text faithfully. A source supports REC content; Labs, Cases and current-state representations are derived. Preserve missing vs absent vs explicitly negative distinctions.
- Case OPEN/CLOSES need owner determination; CONTINUES requires substantive unambiguous evidence. Mere mention is insufficient.
- REC IDs are immutable `REC-YYYYMMDD-NNN`; used and retired NNN must never be reused.
- One mutating operation at a time; logical states `PREPARED -> COMMITTED_REGISTRY -> VALIDATED -> FINALIZED`, or `FAILED`. Validation must encompass both mechanical invariants and operation-scoped semantic checks; failed/ambiguous operations do not silently proceed.
- New active-medication intake must yield one linked, idempotent pending interaction-check *medical-card question*; historic medication migration must not create false new-intake questions. This requirement is independent of whether the writer is Health API or RPC.

## Drive-native rules which must NOT be carried over literally

| Drive-primary implementation | Future PostgreSQL/Sources implementation |
| --- | --- |
| Registry Change Log row occupies the writer slot | `public.operations` active row, enforced by database partial unique index |
| ID Reservations Google Sheet read/reserve/re-read | `public.id_reservations` in a coordinated DB transaction with uniqueness and no reuse |
| REC Google Doc / historical volume; URL in Registry | `public.records.body_text`, `record_id`; Docs URLs only optional historical provenance |
| Google Sheets multi-range logical batch | PostgreSQL ACID transaction(s) with operation-state validation |
| `HEALTH DB/_Staging` and Google Drive moves | Separate file materialization on `HEALTH/Sources` plus idempotent staged/verified source location and compensating recovery |
| Source URL/SHA embedded in Registry | `sources`, `source_locations`, `record_sources` with independently checked bytes/SHA |
| Spreadsheet FORMULA/OPERATION_AUDIT status | DB constraints plus `validation_checks`/`validation_results`, exact operation-bound freshness and semantic evidence |
| Drive revision/Sheets re-read | DB locks/isolation, conditional updates, idempotency and exact post-commit readback |

The old Drive writer's rules remain active *until the separate cutover*. This mapping is a future-design review, **not** authority to modify the old Drive manual or copy the old Google Sheets protocol to the SQL backend.

## What is already in SQL and what is missing

### Verified present (schema in HEALTH/main; partial index also confirmed in live Supabase)

- `public.operations` has the five state values and a **partial unique index** `operations_single_writer_idx ON ((true)) WHERE state IN ('PREPARED','COMMITTED_REGISTRY','VALIDATED')`. Competing active operation rows cannot both commit.
- `id_reservations` has NNN primary key, status shape, links to records and operations; `records.record_id` is primary key, and `records.nnn` is unique.
- FKs/checks and `validation_checks` / `validation_results` provide a structural foundation. `labs.value` / `reference_range` are `text`; normalized source location records exist.
- The one-time full-migration runner specifically checks the active operation and owner authorization, stages data and performs exact final checks.

### NOT established as the routine post-cutover writer contract

1. **A unique active operation does not force all DML through that operation.** Privileged direct `INSERT/UPDATE/DELETE` on medical tables can bypass `operations`. Need role-level restrictions and a tested authorized mutation entrypoint; review protections against bypass/TOCTOU. Do not grant unrestricted `service_role`, owner SQL or PostgreSQL admin rights to AI clients.
2. **Atomic NNN allocator** for new ongoing REC, with row/transaction locking, reservation ownership, retry/idempotency, terminal `used/retired` transitions and no reuse after failed operations. Unique constraints alone only reject collisions.
3. **Business/semantic validation** mapped to DB, not just FK/shape checks. Must bind checks to changed dependencies and current operation, preserve literal laboratory values/precision/provenance, reconcile `Records.case_keys` equivalents, enforce case lifecycle/ID-ledger invariants and rule out stale approvals.
4. **Cross-service Sources workflow:** Google Drive upload/copy cannot participate in PostgreSQL transaction. Need checksum readback, durable operation staging, crash recovery, stable logical source ID, locator verification, conflict handling, no premature `FINALIZED`, and re-entrant reconciliation without deleting originals.
5. **Safe writer authentication and authorization** distinct from browser read-only access; key rotation and audit logs; production implementation must be tested end to end with synthetic fixtures (concurrent writers, failed uploads, partial commits, repeated requests, stale and malicious input).
6. **Medication check invariant** on new active intake: same logical operation, exactly one pending question linked to authoritative REC; must not be silently omitted when changing writer implementation.
7. **Old/new backend boundary:** until cutover, only Drive-native is canonical for normal writes; no dual-write. Before switch, reconcile delta since migration snapshot, confirm full recovery B-04 / replacement-primary A-05 / PWA source opening and owner decision.
8. The SQL change `20261009000000_restrict_service_role_migration_controls.sql` exists in HEALTH/main but was not applied to live Supabase at this review. That is separate migration/security work; writing architecture is not accepted by merely merging docs.

## Deferred candidate A — dedicated Health API

Possible server-side domain service (e.g. Edge Functions or another trusted host): `begin_operation`, `create_record`, `update_record`, `import_labs`, `attach_source`, `add_question`, `update_plan`, `validate_operation`, `finalize_operation`. Own authorization, transactional locking, owner decisions, Source lifecycle, idempotency and recovery. AI clients see domain actions, not arbitrary SQL. **Status: IDEA / NOT IN DEVELOPMENT.**

## Deferred candidate B — PostgreSQL RPC / stored procedures

Potential smaller implementation behind a connector: private-schema functions `health_begin_operation`, `health_create_record`, `health_import_labs`, `health_validate_operation`, `health_finalize_operation`, with limited `EXECUTE` grants to a dedicated writer identity. Functions must check owner authorization and operation ownership, allocate NNN atomically, ensure durable validation and refuse direct table DML by that role. Prefer invoker rights when possible; any necessary elevated function must be narrowly scoped, secured `search_path`, explicitly granted, fully audited and not publicly exposed. Google Drive Source upload still needs a separate orchestrated step and recovery. Verify the actual AI connector can invoke the chosen RPC with a restricted role; generic Supabase SQL admin tools are not evidence. **Status: IDEA / NOT IN DEVELOPMENT.**

## Acceptance before post-cutover AI writes (implementation agnostic)

- A selected and reviewed write contract with least-privilege connector integration, owner authorization and comprehensive automated tests.
- Real concurrency trial: two writers try `PREPARED`, only one succeeds; attempts to bypass active operation cannot mutate medical tables.
- End-to-end REC creation/update, NNN reserve/used/retired, duplicate/retry, Labs text, case links, medication check and Source upload/verification/error recovery tests.
- Operation-scoped validation, audit evidence and post-commit readback; independent backup/restore for the resulting full dataset.
- Explicit owner acceptance of cutover and chosen writing method. No inferred permission to activate writers.

## Governing boundaries and sources

- **Old HealthDB**: active Google Drive `HEALTH DB` Project Manual -> Project State -> Registry. Its medical rules are not edited or replaced here.
- **New HEALTH**: `docs/PROJECT_MANUAL.md`, `docs/PROJECT_STATE.md`, `docs/DATA_MODEL.md`, SQL migration files, and explicit owner decisions.
- This document records the choice to **defer** Health API and SQL RPC implementation and preserve current AI-mediated Drive writes. It is neither production authorization nor implementation acceptance.
