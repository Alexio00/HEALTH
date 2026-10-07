# Backup and Recovery

## Database

Create a daily portable PostgreSQL backup containing:
- schema
- data
- required roles/settings where portable
- manifest
- verification metadata

Prefer `pg_dump` or a compatible Supabase dump path.

## Sources

Use copy semantics, not destructive mirror semantics.

Deleting a primary source must not automatically delete its backup copy.

Track:
- source ID
- checksum
- size
- copy status
- last verified timestamp

## Verification

A backup job is incomplete until verification succeeds.

Minimum verification:
- dump exists and is non-empty
- manifest matches expected artifacts
- source counts/checksums are checked
- periodic restore test succeeds

## Disaster recovery objective

Recovery must be possible from:
1. PostgreSQL backup
2. source backup
3. public code/schema/migrations/docs repository
4. manifests/checksums
5. documented restore procedure

Provider object IDs may change after restore; health IDs and logical links must not.
