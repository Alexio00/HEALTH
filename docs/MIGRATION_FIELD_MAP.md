# Drive-to-HEALTH Migration Field Map

Status: PREPARED. This document is public-safe and contains no medical data, source filenames, private Drive identifiers or credentials.

The active Drive-native HealthDB is the only migration source of truth. Legacy HealthDB GitHub repositories are not migration inputs.

## Global rules

- Final values come from a fresh live Drive snapshot taken immediately before migration.
- Missing, blank and explicitly negative values remain distinct.
- Never reconstruct provenance or laboratory data from nearby rows or similar documents.
- Parse a value into a typed HEALTH column only when the source is unambiguous.
- Preserve non-losslessly-mappable source fields in JSON metadata/provenance.
- Representative MVP rows are not the migration baseline.
- Full migration is staged and validated before replacing representative medical-domain rows.

## Records

| Drive Registry | HEALTH | Rule |
|---|---|---|
| record_id | records.record_id | exact |
| record_id suffix | records.nnn | parse exact three-digit suffix |
| date | records.record_date | parse source date; retain raw text in metadata |
| title | records.title | exact |
| type | records.type | exact |
| record_type | records.record_type | exact |
| confidence | records.confidence | exact |
| status | records.status | exact/null |
| tags | records.tags | parse exact tag tokens into text array |
| tags | record_domains | one relationship per parsed tag |
| summary | records.summary | exact |
| provenance_status | records.provenance_status | exact |
| source_label | records.source_label | exact |
| source_request_id | records.source_request_id | exact |
| source_pages | records.source_pages | exact |
| case_keys | records.metadata.legacy_case_keys | preserve source list |
| record_format | records.metadata.legacy_record_format | preserve exact source value |
| updated_at | records.metadata.source_registry_updated_at | preserve source timestamp |

### Record body

- `google-doc-volume`: extract exactly one RECORD_ID-delimited section from the referenced annual native Google Doc.
- `google-doc`: read the individual native Google Doc for that RECORD_ID.
- Store the cleaned REC body in `records.body_text`.
- Do not infer missing content from another REC or from a legacy repository.

## Domains

| Drive | HEALTH | Rule |
|---|---|---|
| domain | domains.domain_code | exact |
| domain | domains.label | use code as stable label unless a separate authoritative label exists |
| status=active | domains.active=true | exact status mapping |
| status=legacy | domains.active=false | exact status mapping |
| aliases | domains.aliases | parse source aliases into array |
| aliases | metadata.source_aliases_raw | preserve raw source text |
| notes | metadata.source_notes | exact |
| status | metadata.source_status | exact |

## Analytes

| Drive | HEALTH | Rule |
|---|---|---|
| canonical_analyte | analytes.analyte_key | exact |
| display_name | analytes.display_name | exact |
| aliases | analytes.aliases | parse source aliases |
| aliases | metadata.source_aliases_raw | preserve raw |
| notes | metadata.source_notes | exact |

## Sources

For each Registry-linked source:

- copy source bytes from active `HEALTH DB/Sources` into the new `HEALTH/Sources`;
- recompute SHA-256 from actual bytes;
- verify copied size and SHA-256;
- create one `sources` row;
- create a `source_locations` PRIMARY row for the new Drive object;
- retain the old Drive object ID/URL/path in private source metadata as the original locator;
- after independent backup verification, create BACKUP location only from the verified backup object.

Never invent a missing old Registry SHA-256; recompute it from the original file.

The historical retention tree is copied recursively and verified by manifest even when individual files are not Registry-linked.

Known unlinked duplicate-upload quarantine content is excluded from the new canonical primary source tree.

## Record-source relationships

| Drive | HEALTH | Rule |
|---|---|---|
| source_file_urls | record_sources | one row per exact REC↔source association |
| source_pages | record_sources.source_pages | use only when association is unambiguous |
| original Drive URL/ID | record_sources.provenance | preserve original locator |
| source SHA/source label/request context | provenance/source metadata | preserve supported source facts |

Default relationship role remains `evidence` unless the source explicitly supports another role.

## Cases

| Drive | HEALTH | Rule |
|---|---|---|
| case_key | cases.case_key | exact |
| opening_record_id | cases.opening_record_id | exact |
| closing_record_id | cases.closing_record_id | exact/null |
| category | cases.category | exact |
| status | cases.status | exact |
| title | cases.title | exact |
| current_summary | cases.summary | exact |
| start_date | metadata.start_date | preserve exact source value |
| end_date | metadata.end_date | preserve exact source value |
| actual_as_of | metadata.actual_as_of | preserve exact source value |

## Case Links

| Drive | HEALTH | Rule |
|---|---|---|
| case_key | case_links.case_key | exact |
| record_id | case_links.record_id | exact |
| relation | case_links.relation | exact OPEN/CONTINUES/CLOSES |
| date | case_links.relation_date | parse exact source date |
| note | case_links.note | exact/null |

No OPEN/CLOSES decision may be inferred during migration.

## Labs

| Drive | HEALTH | Rule |
|---|---|---|
| record_id | labs.record_id | exact |
| date | labs.observed_on | parse an unambiguous D.M.YYYY / DD.MM.YYYY source date; preserve raw text |
| analyte | labs.analyte_key | exact |
| value | labs.value | literal text, exact |
| unit | labs.unit | exact/null |
| reference_range | labs.reference_range | literal text, exact/null |
| flag | labs.flag | exact/null |
| source_name | labs.source_name | exact |
| note | labs.note | exact/null |
| date | metadata.source_date_text | preserve raw date text |
| — | metadata.literal_preserved=true | migration invariant |

`labs.source_id` is nullable. Populate it only when the specific laboratory row has an unambiguous, supported link to a migrated source object. Do not infer a file merely from a similar source name or from another row.

`lab_id` is regenerated by HEALTH identity. It is not a medical identifier.

## Medications

| Drive | HEALTH | Rule |
|---|---|---|
| medication | medications.name | exact |
| status=active | medications.status=active | exact |
| other supported inactive state | medications.status=inactive | only when source unambiguously indicates inactive |
| dose | medications.dose | exact/null |
| frequency | medications.schedule | exact/null |
| start_date | medications.started_on | parse only exact date |
| end_date | medications.ended_on | parse only exact date |
| route | metadata.route | exact/null |
| record_ids | metadata.source_record_ids | preserve complete source list |
| note | metadata.note | exact/null |

Set `basis_record_id` only when a basis REC is unambiguous from the source. Do not choose the first ID from a multi-ID list by convention.

## Monitoring

Current source snapshot may be empty, but the mapping is defined for future rows:

| Drive | HEALTH | Rule |
|---|---|---|
| item | monitoring.title | exact |
| frequency | monitoring.cadence_text | exact/null |
| status | monitoring.status | map only supported unambiguous state |
| next_date | metadata.next_date | preserve exact source value |
| record_ids | metadata.source_record_ids | preserve complete list |
| note | metadata.note | exact/null |

Set `basis_record_id` only when unambiguous.

## Plan

Current Drive plan due values are mixed: some are exact D.M.YYYY dates and others are free-text scheduling expressions. Only exact dates populate `due_on`; every raw value is preserved.

| Drive | HEALTH | Rule |
|---|---|---|
| action | plan_items.title | exact |
| current active/planned source statuses | plan_items.status=planned | preserve exact source status in metadata |
| exact date due | plan_items.due_on | populate only when source supplies an exact date |
| non-date due text | metadata.due_text | preserve exact; leave due_on null |
| kind | metadata.kind | exact |
| basis | metadata.basis | exact |
| status | metadata.source_status | exact |
| record_ids | metadata.source_record_ids | preserve complete list |

Set `basis_record_id` only when a basis REC is unambiguous. A multi-ID list alone does not authorize choosing one.

## Questions

| Drive | HEALTH | Rule |
|---|---|---|
| question | questions.question | exact |
| open | questions.status=open | exact |
| closed | questions.status=closed | exact |
| created_date | metadata.created_date | preserve exact source value |
| resolved_date | metadata.resolved_date | preserve exact source value |
| record_ids | metadata.source_record_ids | preserve complete source list |
| note | metadata.note | exact/null |

Set `basis_record_id` only when unambiguous.
Set `resolved_by_record_id` only when the source explicitly identifies the resolving REC. Never infer it from a generic record list.

### Specialist questions and medical-card questions

- Existing source Questions / current representative MVP questions are
  preparation questions for specialists per the owner's explicit designation.
  Preserve the exact question text, status, provenance and REC links.
- Do not promote a specialist question to a chart-conflict question.
  The PWA uses question metadata.category=medical_card only for explicit
  internal chart conflicts/actions. Questions without that classification
  are rendered in Visit Preparation, and an explicit specialist prefix is
  used for grouping; unmatched questions go to an unassigned-specialist
  group without fabricating specialty or appointment dates.
- Planned visits are represented by source Plan rows with an explicit
  visit/consultation kind. The Visit Preparation view references those
  plan_items and the question rows; it does not copy data or merge them.
- For future imports, explicit source-supported specialist associations may
  be saved in metadata.visit_specialties. No other clinical evidence may be
  used to invent specialties. A question may have multiple specialties.
- New medication drug-interaction questions are created only by an explicitly
  authorized future intake transaction, never by retrospective migration.


## ID Reservations

The new table includes `metadata jsonb` specifically to preserve old ledger provenance.

| Drive | HEALTH | Rule |
|---|---|---|
| nnn | id_reservations.nnn | exact integer |
| state | id_reservations.state | exact |
| record_id | id_reservations.record_id | exact for used; null for retired |
| retired record_id | metadata.legacy_record_id | preserve exact old identifier because HEALTH retired rows require record_id=null |
| reserved_at | id_reservations.reserved_at | parse exact timestamp/null |
| operation_id text | metadata.legacy_operation_id | exact/null |
| note | metadata.legacy_note | exact/null |

Old text operation IDs MUST NOT be coerced into the new UUID `operation_id`. Old retired record IDs MUST NOT be recreated as active/fake REC rows; they are retained only in metadata while the retired NNN remains unavailable.

At the full-migration snapshot gate there should be no old `reserved` rows because the old single-writer gate must be clear. If a reserved row exists, migration is blocked until the old operation is finalized or failed.

## Timestamps and generated IDs

For operational timestamps generated by HEALTH use a UTC instant in PostgreSQL
and display it as Europe/Moscow. Source dates/timezones are distinct provenance:
preserve exactly and never silently change the time zone. Document formatting
changes are rendered non-destructively from exact source body_text.



- Preserve source timestamps in metadata where the target has no semantically equivalent source field.
- New technical identity IDs for labs/medications/monitoring/plan/questions may be regenerated.
- Do not treat generated HEALTH technical IDs as medical provenance.
- Set HEALTH operational timestamps from the migration operation unless an existing target column explicitly represents the source timestamp.

## Validation rule

Any value that cannot be mapped by the rules above without interpretation remains null in the typed target field and is preserved in metadata/provenance when the source contains it.

No silent coercion is allowed.
