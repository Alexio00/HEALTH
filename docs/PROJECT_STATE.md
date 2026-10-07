# Project State

Status: MVP read-only infrastructure ready; Pages visual verification pending

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
- Exactly one active Supabase Auth user exists.
- Exactly one `app_readers` row exists and maps to that sole active Auth user.
- Auth invariants PASS.
- Database security invariants PASS.
- Simulated authenticated-owner access confirms browser-facing SELECT is allowed.
- Simulated authenticated-owner access confirms INSERT/UPDATE/DELETE are denied.
- Technical tables are not exposed to browser roles.
- Secure default privileges for future `postgres`-owned public tables, sequences and functions are active.
- Static read-only PWA shell is implemented in `frontend/`.
- PWA contains login, Current State, Index, REC and Source routes.
- Service worker does not cache cross-origin/Supabase/Google Drive responses.
- GitHub Pages deployment workflow is committed and a frontend push has triggered the configured workflow path.
- No real medical data has been copied.
- No cutover has occurred.

## Owner-configured settings

- Supabase owner user created.
- Public signup disabled.
- Anonymous sign-ins disabled.
- GitHub Pages source set to GitHub Actions.

The current connector cannot independently read the dashboard-only Auth toggles or list push-triggered GitHub Actions runs. Those settings are owner-confirmed; database-side Auth/RLS behavior is independently verified.

## Pending verification

- Open the public GitHub Pages URL and confirm that the HEALTH login screen renders.
- If it does not, inspect the latest `Deploy HEALTH PWA` GitHub Actions run.

## Next gate

After Pages renders, begin the representative MVP import only under explicit owner authorization for medical-data import. The representative import will be copy-first and limited to a small subset. Full migration remains blocked until explicit owner approval after MVP review.
