# Auth Recovery

HEALTH uses Supabase Auth only for the single browser owner. The accepted complete archive includes all captured database schemas, Auth tables, roles and memberships. Recovery verifies those captured contents and the Auth HTTP lifecycle in isolation. Restoring Auth rows does not recreate provider project settings or signing keys.

## Recovery principle

Do not treat the old Auth user UUID as a medical identifier.

The only HEALTH public table that stores the browser Auth UUID is `app_readers`. Therefore a disaster recovery may create a new owner Auth user and then rebind `app_readers` without changing medical IDs, REC IDs, source IDs, cases, labs or provenance.

## Replacement-provider owner procedure

Use this explicit owner rebind when recovery onto a replacement Supabase service requires a new identity. The daily isolated restore instead tests the captured Auth identity and its HTTP lifecycle. Neither procedure automatically resumes Writer.

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

Credentials and private Auth/session contents must never enter the public repository or public logs. Complete private Auth backups may contain password hashes and session/token records; treat the entire recovery archive as sensitive. Production provider settings, signing keys and external OAuth credentials require their own private provisioning.

## Migration history

Database backups also preserve the `supabase_migrations` schema/history separately. This is technical recovery state and does not replace the canonical timestamped files under `supabase/migrations/`.

## Writer recovery boundary

After exact captured-state verification, recovery disables Writer, clears its accepted code pin and disables upload folders. It preserves the pending journal and medical identity. A recreated Source root and current code acceptance must be verified before a separately accepted resumption. See [complete backup and recovery](BACKUP_AND_RECOVERY.md).
