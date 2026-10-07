# Security

## Public repository

Never commit:
- real medical records
- laboratory values
- source files
- private filenames containing sensitive information
- private storage URLs or object IDs
- production account identifiers
- OAuth tokens
- service-role/secret keys
- database passwords
- backup credentials
- real `.env` files

## Browser

The PWA is read-only.

Allowed:
- public/publishable Supabase client key
- non-sensitive runtime configuration

Forbidden:
- service-role key
- database password
- storage credentials
- AI write credentials

## Database

- public signup disabled
- one administrative user initially
- anonymous users receive no medical data
- authenticated browser access is SELECT-only
- Row Level Security is mandatory on user-facing medical tables

## AI write path

AI clients call controlled server operations. They do not receive raw service-role or unrestricted SQL access.

## Source storage

Source files remain private. Browser source opening relies on the owner's authenticated provider session rather than public source URLs.

## Logging

Do not log medical payloads, raw source contents or secrets into public CI logs.


## Default privileges

HEALTH uses deny-by-default browser exposure for future Postgres objects created by `postgres`:

- future public tables do not automatically grant privileges to `anon` or `authenticated`;
- future public sequences do not automatically grant privileges to `anon` or `authenticated`;
- future public functions do not automatically grant `EXECUTE` to `anon`, `authenticated` or `PUBLIC`;
- `service_role` retains server-side access and must never be exposed to the browser.

The desired SQL state is recorded in `db/migrations/0003_default_privileges.sql`.

After schema or security changes, run `scripts/validation/security_invariants.sql`. It verifies:
- RLS on every public table;
- no public-table privileges for `anon`;
- SELECT-only access for `authenticated` on the explicit browser allow-list;
- safe default privileges for future `postgres`-owned objects.


## Pre-migration Auth gate

Before full migration and again before cutover:

- run `scripts/validation/auth_invariants.sql`;
- run `scripts/validation/security_invariants.sql`;
- verify in the Supabase Auth dashboard that public self-signup / new-user creation is disabled for the project;
- verify only the intended owner account remains active;
- verify the browser still has SELECT-only access and anonymous access remains denied.

The database scripts intentionally fail closed for database/Auth-user invariants. Dashboard-only Auth settings must be checked explicitly because they are not proven by SQL alone.
