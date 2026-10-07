# MVP Plan

## Objective

Build a small vertical slice that proves the new architecture before any full migration.

## Phase 1 — live target bootstrap — PASS

Completed:
- Supabase project connected.
- Core schema applied.
- RLS and browser grants hardened.
- secure default privileges activated.
- exactly one allowed Auth reader registered.
- anonymous table access denied.
- authenticated owner SELECT verified.
- authenticated INSERT/UPDATE/DELETE denied.
- technical tables hidden from browser roles.
- read-only PWA deployed through GitHub Pages.
- owner verified the login screen and successful browser authentication.

## Phase 2 — representative migration subset — NEXT, REQUIRES OWNER IMPORT COMMAND

Select the minimum subset that covers:
- ordinary REC;
- source-linked REC;
- Labs;
- Case relation;
- Plan/Question/Monitoring when practical;
- random REC samples.

Selection rules:
- use only the canonical Drive-native HealthDB as the source;
- preserve existing RECORD_ID values;
- do not allocate replacement IDs for migrated records;
- do not infer missing provenance or medical facts;
- keep Labs value, precision, unit, reference range and source flag literal;
- treat empty, absent and explicit negative values as different states;
- read only Sources required by selected REC;
- record a reproducible selection manifest before import.

## Phase 3 — source copy

Copy only source files required by the MVP into primary target source storage.

For each source:
- create provider-neutral source metadata;
- store physical provider location separately;
- verify the copied object can be opened;
- preserve available checksum/size/provenance metadata.

## Phase 4 — read-only PWA with real MVP data

Verify:
- Current State;
- Index;
- Record;
- Source opening.

Render record text from PostgreSQL, not from the legacy document store.

## Phase 5 — backup / restore

- create an MVP database dump;
- copy MVP source files to independent backup storage;
- verify checksums/counts;
- restore the dump into an empty PostgreSQL target;
- verify restored IDs and relations.

## Phase 6 — acceptance report

Report:
- migrated REC;
- created entities/tables;
- copied sources;
- old -> new comparison;
- validation results;
- auth/RLS results;
- source-link results;
- latency;
- backup/restore result;
- known limitations.

Full migration begins only after explicit owner approval.
