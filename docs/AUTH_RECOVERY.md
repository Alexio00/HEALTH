# Auth Recovery

HEALTH uses Supabase Auth only for the single browser owner. The portable PostgreSQL backup is the recovery source for HEALTH public-schema data, but Auth identity itself is a Supabase-managed service and is recovered explicitly.

## Recovery principle

Do not treat the old Auth user UUID as a medical identifier.

The only HEALTH public table that stores the browser Auth UUID is `app_readers`. Therefore a disaster recovery may create a new owner Auth user and then rebind `app_readers` without changing medical IDs, REC IDs, source IDs, cases, labs or provenance.

## Procedure

After restoring the HEALTH PostgreSQL backup into a replacement Supabase project:

1. Configure the replacement project's Auth settings for private single-owner use.
2. Create exactly one owner user through the Supabase Dashboard/admin path.
3. Confirm the email/account and sign-in method.
4. Ensure public self-signup/new-user creation is disabled.
5. Run `scripts/auth/register_single_reader.sql`.
   - It requires exactly one active Auth user.
   - It registers that user in `public.app_readers`.
   - It removes any stale restored `app_readers` UUID.
6. Run:
   - `scripts/validation/auth_invariants.sql`
   - `scripts/validation/security_invariants.sql`
7. Sign in through the PWA and verify read-only access.
8. Verify anonymous access remains denied and browser INSERT/UPDATE/DELETE remain denied.

## What is intentionally not portable

HEALTH does not depend on preserving the old Auth user UUID, session tokens or browser sessions.

Passwords, refresh tokens, OAuth tokens and secret keys are not stored in the public repository or HEALTH database backup.

## Migration history

Database backups also preserve the `supabase_migrations` schema/history separately. This is technical recovery state and does not replace the canonical timestamped files under `supabase/migrations/`.
