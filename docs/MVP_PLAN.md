# MVP Plan

## Objective

Build a small vertical slice that proves the new architecture before any full migration.

## Phase 1 — live target bootstrap

1. Connect the intended Supabase project.
2. Apply `0001_core.sql` and `0002_rls.sql`.
3. Create the single allowed reader through an administrative path.
4. Verify:
   - anonymous reads fail
   - authenticated SELECT succeeds
   - authenticated INSERT/UPDATE/DELETE fail
   - technical state tables are not exposed to the browser

## Phase 2 — representative migration subset

Select the minimum subset that covers:
- ordinary REC
- source-linked REC
- Labs
- Case relation
- Plan/Question/Monitoring when practical
- random REC samples

Preserve existing RECORD_ID values. Do not allocate replacement IDs for migrated records.

## Phase 3 — source copy

Copy only source files required by the MVP into primary target source storage.

For each source:
- create provider-neutral source metadata
- store physical provider location separately
- verify the copied object can be opened
- preserve available checksum/size/provenance metadata

## Phase 4 — read-only PWA

Implement:
- Current State
- Index
- Record
- Source opening

Render record text from PostgreSQL, not from the legacy document store.

## Phase 5 — backup / restore

- create an MVP database dump
- copy MVP source files to independent backup storage
- verify checksums/counts
- restore the dump into an empty PostgreSQL target
- verify restored IDs and relations

## Phase 6 — acceptance report

Report:
- migrated REC
- created entities/tables
- copied sources
- old -> new comparison
- validation results
- auth/RLS results
- source-link results
- latency
- backup/restore result
- known limitations

Full migration begins only after explicit owner approval.
