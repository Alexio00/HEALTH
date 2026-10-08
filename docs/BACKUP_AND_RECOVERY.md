# Backup and Recovery

## Database

The daily portable PostgreSQL backup contains:

- roles/settings where portable;
- public schema;
- public data;
- Supabase migration-history schema;
- Supabase migration-history data;
- SHA-256 manifest;
- run/commit verification metadata.

The private scheduler uses the official Supabase CLI dump path and verifies every compressed SQL file before upload and again after round-trip download.

The canonical reconstruction history also lives in `supabase/migrations/`. Backup migration-history files preserve the live ledger so disaster recovery can reconcile the restored project with the repository.

## Auth

Supabase Auth identity is recovered explicitly rather than assumed to be part of the public-schema dump.

See `docs/AUTH_RECOVERY.md`.

A replacement owner Auth UUID may differ from the original. This is safe because the only browser-authorization binding in the HEALTH public schema is `app_readers`; the recovery procedure rebinds it after restore.

## Sources

Use copy semantics, not destructive mirror semantics.

Deleting a primary source must not automatically delete its backup copy.

Track and verify:

- source ID;
- checksum;
- size;
- copy status;
- last verified timestamp;
- before/after primary inventory.

## Verification

A backup job is incomplete until verification succeeds.

Minimum daily verification:

- all expected dump files exist and are non-empty;
- SHA-256 manifest matches every dump file;
- the latest backup downloads back successfully;
- round-trip SHA-256 matches;
- source one-way check passes;
- primary Sources inventory remains unchanged.

## Restore drills

A checksum round-trip proves stored bytes, not database restorability.

Perform a real restore drill:

- before full migration if the backup format/tooling changed;
- immediately after the first full-migration backup;
- periodically thereafter;
- after major PostgreSQL/Supabase CLI changes.

A restore drill must use an isolated target, restore the dump, reconcile migration history, execute Auth recovery, run database/security invariants, and compare expected record/source relations and snapshot fingerprints.

For post-full-migration recovery, private backup verification writes operation-bound Source locator and byte evidence into the exact new immutable database backup snapshot. The isolated restore independently reads and SHA-256-checks every linked original from backup against the restored DB. Restore evidence includes the operation UUID, package fingerprint, snapshot ID, independent DB/Source manifest digests, actual GitHub workflow run ID/attempt and exact 15-table fingerprints. Private `SHEDULLER/.github/workflows/finalize-migration.yml` rechecks physical artifacts and authenticated completed run before FINALIZED. An old MVP PASS does not qualify.

For the detailed implementation contract and remaining independent acceptance
steps, see the **private** [SHEDULLER B-04/A-05 recovery audit guide](https://github.com/Alexio000/SHEDULLER/blob/main/docs/AUDIT_B04_A05_RECOVERY.md).
Access is restricted to authorized maintainers. It is the operational reference
for validating a specific post-full-migration backup, Source manifest, restored
snapshot and authenticated restore run; a text-only PASS is insufficient.

## Disaster recovery objective

Recovery must be possible from:

1. PostgreSQL backup;
2. source backup;
3. public code/schema/migrations/docs repository;
4. manifests/checksums;
5. documented Auth recovery;
6. documented restore procedure.

Provider object IDs may change after restore; health IDs and logical links must not.

**A-05 before cutover:** private `SHEDULLER/scripts/relocate_sources.py` implements original Source relocation to a replacement Drive PRIMARY with independent SHA-256 and atomic restored-DB physical locator rebind, preserving canonical source_id. Cutover still requires a real isolated full-dataset loss-of-PRIMARY exercise and opening actual originals through PWA as the replacement owner. Synthetic code tests cannot replace this acceptance gate.

## Retention

Backup deletion is intentionally not automated by the current copy-first scheduler. Introduce destructive retention only under a separate owner-approved policy. Until then, monitor backup storage growth and keep timestamped database backups immutable.
