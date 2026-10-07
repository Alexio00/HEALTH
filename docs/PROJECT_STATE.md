# Project State

Status: MVP read-only gate PASS; representative import authorization pending

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
- Authenticated owner SELECT succeeds.
- Authenticated browser INSERT/UPDATE/DELETE are denied.
- Technical tables are not exposed to browser roles.
- Secure default privileges for future `postgres`-owned public tables, sequences and functions are active.
- Static read-only PWA is implemented and deployed through GitHub Pages.
- Owner confirmed the public Pages URL renders and successful authentication completes in the browser.
- PWA contains login, Current State, Index, REC and Source routes.
- Service worker does not cache cross-origin/Supabase/Google Drive responses.
- No real medical data has been copied.
- No cutover has occurred.

## Owner-configured settings

- Supabase owner user created.
- Public signup disabled.
- Anonymous sign-ins disabled.
- GitHub Pages source set to GitHub Actions.

The current connector cannot independently read the dashboard-only Auth toggles or list push-triggered GitHub Actions runs. Those settings are owner-confirmed; database-side Auth/RLS behavior and browser authentication are independently verified.

## Next gate

Representative MVP import is ready to begin, but real medical data may be copied only after an explicit owner import command.

The representative import will:
- remain copy-first;
- keep the current Drive-native HealthDB canonical;
- preserve existing RECORD_ID values;
- use a small representative subset only;
- copy only Sources required by that subset;
- validate old -> new content, provenance, links, Labs literals and Case relations;
- stop before any full migration or cutover.

Full migration remains blocked until explicit owner approval after MVP review.
