# HEALTH

Private-data-safe public codebase for a personal health record system.

## Scope

This repository contains only application code, database schema/migrations, API contracts, tests, deployment logic, and synthetic fixtures. It must never contain real medical records, laboratory results, source documents, private storage identifiers, credentials, secrets, or production configuration values.

## Target architecture

- PostgreSQL (Supabase-compatible) as the canonical structured database.
- Provider-neutral source model: logical source identity is separated from physical storage location.
- Read-only PWA hosted on GitHub Pages.
- Until cutover, ordinary owner-authorized AI writes stay in the canonical Drive-native HealthDB.
- Future post-cutover AI writes require a controlled, least-privilege write path; dedicated Health API and restricted PostgreSQL RPC/connector are deferred options, not currently in development.
- Independent backups of database and source files.
- Scheduled jobs live outside this public repository.
- The legacy/current health database remains authoritative until an explicit cutover.

## Repository layout

- `docs/` — architecture, data model, security, migration, recovery and project state.
- `supabase/migrations/` — canonical timestamped Supabase migration history.\n- `db/migrations/` — earlier aggregated migration snapshots retained for reference.
- `db/tests/` — schema/invariant tests.
- `api/` — future Health API contract/design notes; no routine write service implemented.
- `frontend/` — read-only PWA.
- `scripts/migration/` — fail-closed full-migration package/staging/fingerprint tooling.
- `scripts/validation/` — validation tooling.
- `tests/` — integration/e2e tests.
- `.github/workflows/` — public-repository workflows that are safe without medical data.

## Security boundary

Use aliases and environment variables for operational accounts and provider identifiers. Commit only `.env.example`, never real `.env` files.

Real health data must stay in the configured private database and private source storage.
