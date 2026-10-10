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

5. **Owner-authorized AI writing — current and deferred options**
   - **now, until cutover:** ordinary ChatGPT/AI changes continue only in the active Drive-native HealthDB through its connected Google Drive workflow and governing Manual/State;
   - **new HEALTH MVP:** the PWA and ordinary AI consumption remain read-only; the owner-gated full-migration executor is not a general write service;
   - **potential later option A:** a dedicated controlled Health API for AI writers, NOT IN DEVELOPMENT;
   - **potential later option B:** limited PostgreSQL RPC/stored procedures callable through a suitably permissioned AI connector, NOT IN DEVELOPMENT;
   - before post-cutover medical writes, a selected implementation must enforce authorized single-writer operations, immutable IDs, validation, source lifecycle and least privilege. Neither option is automatically accepted simply because a general SQL connector exists;
   - see [write-path decision and rule mapping](WRITE_PATH_DECISION.md) and [API alternatives](API.md).

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

The Drive-native HealthDB remains authoritative until explicit cutover. Full migration is copy-first and does not delete or rewrite the source system.
