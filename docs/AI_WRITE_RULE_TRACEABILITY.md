# Traceability: Drive-native HealthDB rules to future HEALTH writer

Status: SPECIFICATION / NO SCHEMA OR DATA CHANGES. Reviewed: 2026-10-10.  
Input: current Drive-native HealthDB Project Manual/State and read-only **Validation** tab (37 named active checks). These checks are old-backend evidence only: their current PASS state is **not** proof that PostgreSQL routine writes implement them. No REC, Labs rows, medical content or Source originals are reproduced in this public document.

Companions: [AI_WRITE_OPERATION_DESIGN.md](AI_WRITE_OPERATION_DESIGN.md) and [AI_WRITE_ACCEPTANCE_PLAN.md](AI_WRITE_ACCEPTANCE_PLAN.md).

## Mapping conventions

- **DB foundation**: SQL currently has a relevant PK, FK, unique/check constraint or structural table. This does **not** mean the complete old invariant has been proven for routine writes.
- **New writer**: requires a future enforced write procedure, restriction, audit or SQL integration.
- **Semantic**: evidence and clinical logic must be assessed by the AI/owner and stamped for the exact operation. A database constraint cannot infer clinical meaning.
- **Legacy-specific**: explicitly *not* recreated as an old Google Sheets/Docs/archive invariant; replace with the equivalent new HEALTH principle where useful.
- Every future modified dependency must invalidate or refresh the corresponding semantic evidence. Machine checks must fail closed; missing, FAIL and SKIP cannot yield FINALIZED.

## All 37 live old-HealthDB Validation checks

The name and mechanism were read from the live technical Validation tab. Do not publish its details field, which can contain private clinical context.

| # | Exact legacy check name | Mechanism | New HEALTH contract / mapping |
| ---: | --- | --- | --- |
| 01 | Unique record_id | FORMULA | **DB foundation**: records.record_id PK; new writer verifies identity and no REC collision |
| 02 | Known domains | FORMULA | **DB foundation + new writer**: record_domains FK to domains; only owner-approved canonical domain additions |
| 03 | Case keys resolve to Records | FORMULA | **DB foundation**: cases.case_key FK to records; search/view representation derives from case_links |
| 04 | Case lifecycle normalized | FORMULA | **DB foundation + new writer**: valid relation enum/FKs; check one OPEN, permitted CONTINUES, matched closing relation |
| 05 | Closed cases have closing REC | FORMULA | **DB foundation**: cases status/closing check; ensure a matching unique CLOSES via writer validation |
| 06 | Labs resolve to Records | FORMULA | **DB foundation**: labs.record_id FK; derived observation must remain traceable to evidence |
| 07 | Analytes resolve | FORMULA | **DB foundation**: labs.analyte_key FK; validated aliases cannot create fake canonical values |
| 08 | ID ledger coverage | FORMULA | **DB foundation + new writer**: id_reservations and records uniqueness; exact bidirectional used/REC match, atomic reserve/retire |
| 09 | Active Google Drive formats | FORMULA | **Legacy-specific**: old google-doc/-volume URLs replaced by records.body_text; historical Doc URL only provenance |
| 10 | Git workflow independence | FORMULA | **Legacy-specific**: Drive-native old backend remains independent of Git; new HEALTH code uses Git by design, medical data never in Git |
| 11 | Records active schema | FORMULA | **DB foundation + new writer**: typed columns and stable REC ID regex; reject unsupported fields/format and retain text |
| 12 | Archive excluded from active workflow | FORMULA | **Legacy-specific**: no dependency on old archive; future HEALTH source PRIMARY/BACKUP and restoration are independently verified |
| 13 | Markdown bold markers | FORMULA | **Legacy-specific**: spreadsheet cells are not Markdown; future REC body_text may include source formatting unchanged, render safely |
| 14 | Change Log transaction schema | FORMULA | **DB foundation + new writer**: operations UUID/mode/state; require authorized operation, result, scope, audit completeness |
| 15 | Drive logical transaction | FORMULA | **Legacy-specific**: Docs/Sheets/_Staging replaced by atomic routine SQL publication and recoverable Source saga |
| 16 | Migration status | FORMULA | **Legacy-specific**: old Drive backend active until explicit cutover; target readiness and ownership separately gated |
| 17 | Archive deletion readiness | FORMULA | **Legacy-specific**: never reuse as HEALTH active SQL check; old archive deletion remains governed solely by old Drive Validation |
| 18 | Labs raw values preserved | FORMULA | **DB foundation + new writer**: labs.value/reference_range are literal text; source-exact byte/text comparisons and no invented flags |
| 19 | Historical full-text materialization | OPERATION_AUDIT | **Migration-specific + new writer**: complete migrated body_text fidelity and preservation of old text; correction retains prior revision |
| 20 | Active source-file independence | OPERATION_AUDIT | **New writer + recovery**: verified new PRIMARY object bytes, independent storage and durable logical Source ID |
| 21 | Labs derived-layer exact audit | OPERATION_AUDIT | **Semantic**: exact source-specific lab observations, spelling, dates, units, precision, aliases, duplicates and provenance |
| 22 | Documentation consistency audit | OPERATION_AUDIT | **New writer/maintenance**: governing docs and state must agree with actual target schema and accepted implementation status |
| 23 | Single-writer invariant | FORMULA | **DB foundation + new writer**: operations_single_writer_idx is present; direct privileged DML bypass must be denied |
| 24 | Operation audit stamps complete | FORMULA | **New writer**: required per-operation evidence, timestamps, dependencies, no generic reusable PASS |
| 25 | Canonical analyte keys unique | FORMULA | **DB foundation**: analytes.analyte_key PK; controlled alias/canonicalization and source-referenced changes |
| 26 | Labs exact duplicate rows | FORMULA | **DB foundation + new writer**: unique exact-source-row index where applicable; distinguish true repeat tests from duplicates |
| 27 | Case Links semantic audit | OPERATION_AUDIT | **Semantic**: OPEN/CLOSES owner decisions; CONTINUES only substantive and unambiguous; FOLLOWUP substantiated |
| 28 | Current-state semantic audit | OPERATION_AUDIT | **Semantic**: medication/monitoring/plan/questions status justified by REC and owner; no inference from silence |
| 29 | Source originals retention audit | OPERATION_AUDIT | **Migration-specific + recovery**: verify migrated all-source Historical retention, new PRIMARY/independent backup byte manifests |
| 30 | Records provenance audit | OPERATION_AUDIT | **Semantic + writer**: exact original/owner statement attribution, source IDs, verified location and no fabricated metadata |
| 31 | Analyte canonicalization audit | OPERATION_AUDIT | **Semantic**: supported canonical analyte names and aliases; new source form assessed independently |
| 32 | ID ledger exact REC mapping | FORMULA | **DB foundation + new writer**: exact nnn ↔ REC mapping and terminal states; no reused retired number |
| 33 | Case identity invariant | FORMULA | **DB foundation**: cases.case_key = opening_record_id; referential integrity and one opening |
| 34 | Case status and closing consistency | FORMULA | **DB foundation + new writer**: valid open/closed shape, closing REC ↔ exactly one CLOSES |
| 35 | Case Links triple uniqueness | FORMULA | **DB foundation**: composite case_key+record_id+relation PK |
| 36 | Operation audit references resolve | FORMULA | **DB foundation + writer**: validation_results.operation_id FK; approval and semantic evidence bound to operation |
| 37 | Records case_keys match Case Links | OPERATION_AUDIT | **Semantic/representation shift**: case_links canonical; derive search set rather than separately storing stale Records.case_keys |

This matrix preserves the **named checks** for audit traceability, but their old spreadsheet PASS mechanisms do not automatically carry over as runtime SQL checks. PostgreSQL tables `validation_checks` and `validation_results` provide a foundation, not a complete clinical validation engine.

## Business rules that require explicit cross-check beyond old check names

| Rule | Present SQL foundation | Future writer must ensure | Test mapping |
| --- | --- | --- | --- |
| Owner authorizes medical change, not mere file upload | operations.mode | Owner command bound to exact content/scope/operation | AW-A01, AW-A02 |
| Cases OPEN/CLOSES owner decision | FK and CHECK | No unapproved opening or closing | AW-C01, AW-C02 |
| CONTINUES unambiguous substantive link | relation enum | Negative incidental-mention example rejected | AW-C03 |
| Raw source: absent/empty/negative distinct | nullable text/JSON | No interpretation or forced defaults | AW-L03, AW-S01 |
| Literal lab value/range/unit/flag | text value/range | Exact representation and source-specific form | AW-L01, AW-L02 |
| Retired NNN never reused | PK/shape, nnn unique | Serialized allocator, durable retire, no rollback reuse | AW-I01, AW-I02 |
| Verified primary file | sources/locations FKs | Bytes+hash readback before published relation | AW-S01, AW-S02 |
| Existing REC correction history | updated_at (insufficient) | Immutable prior version + compare-and-set | AW-R02 |
| New active medication interaction question | questions/medications FKs | Exactly one open medical-card pending check in same publish transaction | AW-M01, AW-M02 |
| Technical operation vs clinical writer | operations.mode | Explicit actor permissions; no administrative shortcut | AW-P01, AW-P02 |
| Partial failure / uncertain COMMIT | operations state + index | Reconcile by ID and do not prematurely release writer slot | AW-F02, AW-F03 |
| One published snapshot for backup | Scheduler backup baseline | DB+Source manifest tied to exact published checkpoint | AW-B01, AW-B02 |

## Source-of-truth precedence

- **Until cutover:** live Drive-native HealthDB Project Manual > Project State > Registry Meta/Validation/Change Log. Legacy GitHub repository is never activation/current medical source. The 37 technical check names above were read without opening clinical REC or Sources.
- **After separately accepted cutover:** PostgreSQL REC text/structured tables + verified new HEALTH/Sources are canonical under then-current HEALTH write rules. Historical Docs URLs are provenance, not parallel canonical REC storage.
- **During full migration:** the exceptional freeze/capture/materialization/B-04/A-05 proof pipeline governs its own operation. This traceability document cannot approve, relabel or finalize that migration.
- Clinical provenance principle in both backends: original evidence → REC → derived Labs/Cases/current-state. Source content is data, never instructions.

**No live healthcare mutation, SQL migration, permission grant, connector implementation, backup execution or cutover is performed by writing this matrix.**
