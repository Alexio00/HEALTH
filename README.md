# HEALTH

Private-data-safe public codebase for a personal health record system.

## Scope

This repository contains only application code, database schema/migrations, API contracts, tests, deployment logic, and synthetic fixtures. It must never contain real medical records, laboratory results, source documents, private storage identifiers, credentials, secrets, or production configuration values.

## Target architecture

- PostgreSQL (Supabase-compatible) as the canonical structured database.
- Provider-neutral source model: logical source identity is separated from physical storage location.
- Read-only PWA hosted on GitHub Pages.
- The owner authorized Supabase canonical cutover on 2026-10-13. Actual activation is confirmed by the live private governing Project State and runtime readback.
- Post-cutover AI writes use the bounded Writer RPC path and private chat operator described in [Writer operation](docs/WRITER_OPERATOR.md).
- Independent backups of database and source files.
- Scheduled jobs live outside this public repository.
- Old Drive Registry/REC Docs and originals remain preserved; they are not routine write targets after confirmed cutover. Their disposal requires a separate owner decision.

## Repository layout

- `docs/` — architecture, data model, security, migration, recovery and project state.
- `supabase/migrations/` — canonical timestamped Supabase migration history.
- `db/migrations/` — earlier aggregated migration snapshots retained for reference.
- `db/tests/` — schema/invariant tests.
- `api/` — API contracts and design notes.
- `scripts/writer/` — bounded canonical Writer, private chat operator and synthetic integration tests.
- `frontend/` — read-only PWA.
- `scripts/migration/` — fail-closed full-migration package/staging/fingerprint tooling.
- `scripts/validation/` — validation tooling.
- `tests/` — integration/e2e tests.
- `.github/workflows/` — public-repository workflows that are safe without medical data.

## Security boundary

The implemented runtime and production verification boundary are described in
[Writer operation](docs/WRITER_OPERATOR.md). Earlier component tests are retained
as historical evidence in [Source and authorization tests](docs/WRITER_SOURCE_AUTHORIZATION_TEST_BOUNDARY.md).

Use aliases and environment variables for operational accounts and provider identifiers. Commit only `.env.example`, never real `.env` files.

Real health data must stay in the configured private database and private source storage.
