# Project State

Status: MVP bootstrap

## Confirmed

- Public repository initialized.
- Repository is intentionally safe for public inspection.
- Primary source target folder exists.
- Independent backup root exists.
- Backup subfolders for Sources and Database exist.
- Existing health database remains the migration source and source of truth.

## Not yet complete

- Supabase project access is not connected to this working session.
- Private scheduler repository is not visible to the current GitHub connection.
- PostgreSQL migrations have not yet been applied to a live database.
- Authentication/RLS has not yet been validated against a live Supabase project.
- PWA has not yet been deployed.
- No real medical data has been copied.
- No cutover has occurred.

## Next gate

Connect the intended Supabase project, then apply migrations to an isolated MVP database and import a small representative subset only.
