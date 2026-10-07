# Project State

Status: MVP infrastructure ready; owner Auth/Pages toggles pending

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
- Database security invariants are encoded and currently PASS.
- Static read-only PWA shell is implemented in `frontend/`.
- PWA contains login, Current State, Index, REC and Source routes.
- Service worker does not cache cross-origin/Supabase/Google Drive responses.
- GitHub Pages deployment workflow is committed.
- No real medical data has been copied.
- No cutover has occurred.

## Owner actions pending

- Create the sole Supabase Auth user with email/password and auto-confirm it.
- Disable "Allow new users to sign up" and anonymous sign-ins in Supabase Auth.
- In GitHub repository Settings -> Pages, set Source to GitHub Actions.

## After owner actions

- Register the sole active Auth user in `public.app_readers` using `scripts/auth/register_single_reader.sql`.
- Run `scripts/validation/auth_invariants.sql` and database security invariants.
- Verify anonymous denial, owner SELECT, and browser write denial end-to-end.
- Verify GitHub Pages deployment and mobile/PWA shell.

## Remaining MVP work

- Import a small representative subset only.
- Copy only the source files needed by that subset.
- Validate content, navigation, mobile behavior and latency.
- Implement portable database and Sources backup jobs.
- Verify restore and backup manifests/checksums.
- Produce the MVP acceptance report for owner review.

## Next gate

Complete the three owner-side Auth/Pages settings above, then finish end-to-end read-only verification. Full migration remains blocked until explicit owner approval after MVP review.
