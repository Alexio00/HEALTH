# Full Migration Plan

Status: PREPARED FOR OWNER AUTHORIZATION

This document defines the procedure for migrating the active Drive-native HealthDB into the new HEALTH platform. It intentionally contains no medical records, laboratory values, source filenames, private Drive identifiers, credentials or secrets.

## Source of truth

The only migration source of truth is the active Google Drive workspace:

- HealthDB Registry;
- HEALTH DB/Records;
- HEALTH DB/Sources;
- HEALTH DB/Project.

Legacy HealthDB GitHub repositories are outside the active workflow and MUST NOT be used as an activation source, migration source of truth, ID allocator, change-control system or write target.

The current Drive-native HealthDB remains canonical until a separately authorized cutover.

## Authorization boundary

Preparing this plan does not authorize full migration or cutover.

Full migration starts only after an explicit owner command.
Cutover requires a second explicit owner decision after full migration validation.

The target HEALTH migration operation uses a UUID. The old Drive-native freeze uses the existing legacy Change Log ID format (`MAINT-…`/equivalent). These identifiers belong to different systems and must not be coerced into one format.

## Final snapshot gate

Immediately before full migration:

1. Read the active Project State and Project Manual.
2. Require the old Drive-native single-writer gate to be clear: zero unfinished mutating operations.
3. Create one dedicated old-HealthDB maintenance Change Log row for the migration freeze in state `PREPARED`; it creates no ID reservation.
4. Reread the old Change Log and require that freeze row to be the sole unfinished operation.
5. Require all live FORMULA validations to PASS while the freeze is held.
6. Run the private scheduler capture extractor under that freeze. It must export a fresh Registry snapshot, deterministically extract every REC body from the active individual/annual Google Docs, read every Registry-linked source from active `HEALTH DB/Sources`, recompute source size/SHA-256 from bytes, and capture a fresh recursive Historical Sources manifest.
7. Materialize Registry-linked source bytes into the new `HEALTH/Sources`, verify copied size/SHA-256 by round-trip, and require the package PRIMARY source locations to point only to those new objects. Retain old Drive IDs/URLs only in private provenance.
8. Record the snapshot timestamp, all entity counts, the legacy freeze operation ID/state, and zero **other** unfinished operations privately in package schema v2 together with `capture_mode=migration` and `source_location_mode=new-health-primary`.
9. Recompute the migration set from that snapshot. Never rely on an earlier MVP or planning count.
10. Keep the same freeze row `PREPARED` through staging and until the target HEALTH commit gate.
11. Immediately before target commit, re-export the Registry and reread the old Change Log; require an unchanged canonical Registry fingerprint and the same legacy freeze operation to still be `PREPARED` and the sole unfinished operation.

If the freeze is missing, changed, no longer sole, or the old HealthDB changes before commit, abort the target commit, discard the staged result and rebuild from a fresh frozen snapshot. Release/finalize the old freeze only after the target exact post-commit comparison and required validation have completed.

## Representative MVP handling

The existing new HEALTH data is representative test data, not a migration baseline.

The full migration MUST rebuild the medical domain from the final Drive snapshot rather than applying an assumed delta to the representative MVP.

Technical tables and Auth configuration are preserved.
Representative medical-domain rows are replaced by the validated full snapshot inside the controlled migration operation.

## Source files

### Registry-linked originals

For every source referenced by the final Registry snapshot:

1. Read the original from active HEALTH DB/Sources.
2. Compute the checksum from the actual source bytes.
3. Copy the source into the new HEALTH/Sources tree.
4. Verify copied size and checksum.
5. Create the HEALTH source row.
6. Store the new Drive object as source_locations role PRIMARY.
7. Retain the old Drive object identifier/URL in private source metadata or record-source provenance as the original locator.

Do not invent a checksum when the old Registry field is blank.

### Historical retention tree

The active HEALTH DB/Sources/Historical tree is retained as source evidence/recovery material even when individual files are not directly linked from a Registry REC.

Its hierarchy is copied non-destructively and verified by a recursive manifest.

### Exclusions

Known unlinked duplicate-upload quarantine folders are not canonical migration inputs. They remain recoverable in the old workspace/backup but are excluded from the new primary source tree unless a later validation proves a unique source exists only there.

### Backup location

After PRIMARY copies are verified, the backup scheduler copies the new HEALTH/Sources tree to the independent backup Google Drive.

Where HEALTH source rows require a BACKUP location, populate it only from verified backup objects. Never infer a backup object ID.

## Structured migration order

Load into an isolated staging area first.

Recommended dependency order:

1. domains and canonical analytes;
2. records;
3. record-domain relationships;
4. sources and PRIMARY source locations;
5. record-source relationships and provenance;
6. cases;
7. case links;
8. laboratory observations;
9. medications;
10. monitoring;
11. plan items;
12. questions;
13. the complete record-ID reservation ledger, including retired identifiers.

Preserve literal laboratory value and reference-range text exactly.

## Record text

Historical Drive-native record volumes remain the source of full text for migrated historical REC.

The migration process must extract each RECORD_ID section deterministically from its Drive-native annual volume and store only that REC body in the new record row.

New or individually materialized REC are read from their native Google Docs.

No content may be reconstructed from neighboring REC, a similar form, or a prior repository snapshot.

## Staging validation

Before public medical-domain tables are replaced, staging must prove at least:

- every old REC is represented exactly once;
- no extra REC exists;
- every used ID-ledger entry resolves to exactly one REC;
- retired identifiers remain unavailable;
- all domain references resolve;
- all case identities and links resolve;
- case lifecycle relations retain their exact relation type;
- every laboratory row resolves to a REC and analyte;
- no exact duplicate laboratory row is introduced;
- laboratory raw value/reference text matches the final Drive snapshot;
- all plan/question/medication/monitoring rows match the final Drive snapshot;
- every Registry-linked source is copied and checksum-verified;
- every record-source relationship resolves;
- the historical retention manifest is complete;
- known unlinked duplicate uploads are not introduced into the new canonical source set;
- browser RLS remains read-only;
- anonymous access remains denied.

Any mismatch blocks commit.

## Commit model

Commit the validated staged medical domain in one controlled migration operation.

Do not mix migration with frontend, Auth or unrelated schema work.

After commit:

1. rerun all FORMULA validations;
2. rerun all migration-impacted OPERATION_AUDIT checks;
3. run the migration runner exact table-fingerprint comparison against the sealed final Drive snapshot; counts alone are insufficient;
4. verify source PRIMARY copies;
5. verify independent backup state;
6. keep the old Drive-native HealthDB unchanged and canonical until owner cutover.

## Post-migration delta

If the owner continues to use old HealthDB after a full migration but before cutover, any subsequent old-HealthDB changes form a new delta.

Before cutover, perform a final change check against the migration snapshot and migrate/validate that delta.

Cutover is forbidden while an unapplied delta exists.

## Rollback

Before cutover, rollback means discarding/replacing the new HEALTH medical-domain migration result. It must never require deleting or rewriting the canonical old Drive-native HealthDB.

## Cutover gate

Cutover is a separate owner decision.

Only after:
- full migration PASS;
- source verification PASS;
- independent backup PASS;
- final post-migration delta = empty;
- owner review/acceptance;

may the owner authorize the new HEALTH platform as canonical.

Until then, Google Drive HealthDB remains the source of truth.


## Deployment-region gate

Before owner authorization for full migration, the owner must explicitly accept the current Supabase primary region or authorize migration to another region.

Region choice is intentionally not inferred by automation because changing regions requires a project migration and materially changes data residency/latency.

The chosen region decision must be recorded in private HEALTH technical state before full migration begins.
