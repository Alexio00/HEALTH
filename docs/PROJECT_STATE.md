# Project State

Status: MVP infrastructure ready for representative migration

## Confirmed

- Public repository `Alexio00/HEALTH` initialized and intentionally safe for public inspection.
- Private scheduler repository `Alexio000/SHEDULLER` connected with administrative/write access.
- Scheduler repository initialized with a README and a GitHub Actions smoke workflow.
- Primary source target folder exists.
- Independent backup root exists.
- Backup subfolders for Sources and Database exist.
- Existing Drive-native HealthDB remains the migration source and source of truth until explicit cutover.
- Supabase project `HEALTH` is connected and healthy.
- Core PostgreSQL schema is applied to the live MVP database.
- Row Level Security is enabled on every public table.
- `anon` has no public-table privileges.
- `authenticated` has SELECT-only access to the explicit browser-facing allow-list.
- Technical tables are not exposed to browser roles.
- Secure default privileges for future `postgres`-owned public tables, sequences and functions are active.
- Database security invariants are encoded in `scripts/validation/security_invariants.sql` and currently PASS.
- No real medical data has been copied.
- No cutover has occurred.

## Remaining MVP work

- Configure single-user authentication and register the approved reader identity.
- Import a small representative subset only.
- Copy only the source files needed by that subset.
- Build the first read-only PWA path: Current State -> Index -> REC -> Source.
- Validate content, navigation, mobile behavior and latency.
- Implement portable database and Sources backup jobs.
- Verify restore and backup manifests/checksums.
- Produce the MVP acceptance report for owner review.

## Next gate

Move from infrastructure maintenance into the representative MVP import only when the import operation begins. Full migration remains blocked until explicit owner approval after MVP review.
