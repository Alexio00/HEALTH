# Architecture

## Goal

HEALTH separates application code, structured health data, original source files, backups, authentication and scheduled automation.

## Components

1. **Public code repository**
   - canonical timestamped Supabase migration history;
   - schema/validation/migration tooling;
   - read-only PWA;
   - tests and deployment logic;
   - synthetic fixtures only.

2. **PostgreSQL / Supabase**
   - canonical structured HEALTH data after cutover;
   - operation state and private validation evidence;
   - provider-neutral source metadata;
   - no dependency on Google Drive paths as medical identifiers.

3. **Private source storage**
   - original medical source files;
   - logical source IDs separated from physical provider-location rows.

4. **Read-only PWA**
   - authenticated owner only;
   - reads PostgreSQL through Supabase Auth/PostgREST;
   - first-party committed frontend JavaScript only;
   - no runtime third-party JavaScript CDN;
   - never writes medical data;
   - stable HEALTH IDs in application routes.

5. **Owner-authorized AI writing — implemented bounded SQL path**
   - conversational owner requests remain the interface;
   - the private chat operator prepares exact intents/candidates using restricted RPC; separate verifier credentials provide current semantic/literal-lab/Source evidence;
   - signed GitHub owner authorization binds the exact accepted main commit and digest; no medical payload or service key is given to the ordinary Writer;
   - accepted canonical cutover was authorized on 2026-10-13; confirm actual activation through the private live Project State/runtime;
   - old Drive Registry/REC Docs remain preserved snapshots and are not dual-write targets;
   - PWA remains read-only; a dedicated Health API is an optional future choice;
   - see [Writer operation](WRITER_OPERATOR.md) and [current documentation map](CURRENT_DOCUMENTATION.md).

6. **Independent scheduler**
   - private repository;
   - database backups;
   - source backups;
   - backup verification;
   - read-only keepalive.

7. **Supabase Auth**
   - single browser owner;
   - browser authorization bound through `app_readers`;
   - Auth identity recovery is explicit and independent of medical identifiers.

## Trust boundaries

- Browser: publishable Supabase key and owner session only.
- Public GitHub: no medical data, private provider locators, credentials, backup payloads or production secrets.
- Private scheduler: secrets in GitHub Actions secret storage only; medical filenames/dump contents are not published in logs/artifacts.
- Source provider identifiers are operational locators, not medical identifiers.

## Reproducibility

- `supabase/migrations/` is the canonical timestamped schema history.
- `db/migrations/` contains earlier aggregated migration snapshots retained for reference.
- security/Auth invariants are executable SQL.
- full migration is executable through `scripts/migration/full_migration.py`, not hand-built data SQL.

## Portability and recovery

- database is backed up as portable roles/schema/data plus Supabase migration history;
- source identity survives storage-provider movement;
- Auth owner identity may be recreated and rebound through `app_readers`;
- PWA can move to another static host;
- provider-specific source location logic stays outside medical identity.

## Current source-of-truth boundary

The owner authorized canonical Supabase cutover on 2026-10-13. Its actual completion is governed by private Project State/runtime readback. Full migration was copy-first; old medical data, original files and snapshots are retained until a separate disposal decision.
