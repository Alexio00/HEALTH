# Data Model

## Core principles

- Stable health IDs are independent of storage providers.
- Structured medical data lives in PostgreSQL.
- Original source files stay in private object/file storage.
- Provider IDs are locators only.
- Provenance is explicit.
- Current-state tables remain traceable to source records.

## Main entities

### records
Canonical REC metadata and full renderable text for the new system.

Key fields:
- `record_id`
- `nnn`
- `record_date`
- `title`
- `record_type`
- `summary`
- `body_text`
- `status`
- `confidence`
- `provenance_status`
- `metadata`

### sources
Logical source identity:
- `source_id`
- `logical_path`
- original filename
- MIME type
- byte size
- SHA-256
- source date
- metadata

### source_locations
Physical provider locator:
- `source_id`
- provider
- account alias
- provider object ID
- role: PRIMARY/BACKUP

### record_sources
Many-to-many REC ↔ source mapping with page/provenance metadata.

### cases / case_links
Normalized cases and OPEN / CONTINUES / CLOSES / FOLLOWUP relations.

### analytes / labs
Canonical analyte dictionary plus raw laboratory observations.
`labs.value` and `labs.reference_range` are text by design.

### medications / monitoring / plan_items / questions
Current-state layers with explicit basis REC links.

Visit Preparation is a view over plan_items (explicit planned visits)
and questions (specialist discussion items), not a duplicate storage entity.
Question metadata.category=medical_card is reserved for chart conflicts/actions;
metadata.visit_specialties stores only explicit specialist associations.
The absence of a matching plan item never authorizes inventing an appointment.

New active medications require an idempotent, transactionally linked pending
medical-card drug-interaction check. Any future authorized post-cutover AI write
path must enforce this invariant, whether implemented through a dedicated
Health API or a restricted PostgreSQL RPC/connector. Neither implementation
is currently in development or approved for production writes. Migration of
existing medications must not create false new-prescription alerts.

### operations
Single-writer logical transaction state.

### id_reservations
Technical NNN ledger preserving used/reserved/retired semantics.

### validation_checks / validation_results
Machine and semantic validation evidence per operation.

## Deliberate differences from the Drive-native model

- Google Docs URLs are not canonical record storage.
- REC renderable text is stored in the database for the new frontend.
- Source provider locations are normalized away from logical source identity.
- PostgreSQL constraints replace spreadsheet-only integrity checks where possible.
