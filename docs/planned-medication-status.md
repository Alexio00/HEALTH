# Planned medication status

The owner authorized preserving legacy `planned` medications in the main status
column on 2026-10-10. The canonical migration widens the existing CHECK to
`active`, `inactive`, `planned`; it changes no rows, RLS policies, grants or Auth.
The public package validator rejects statuses outside these three values.

`db/migrations/0001_core.sql` is also updated for fresh standalone PostgreSQL
fixtures. Existing Supabase deployments must use the new canonical migration;
the already-applied canonical core migration is unchanged.

The private capture adapter must preserve `planned` and the original source
status, and recovery must require the exact current canonical migration ledger
for FULL backups while recognizing explicitly enumerated old MVP ledgers.
This schema change alone does not prove full migration, recovery or FINALIZED.
