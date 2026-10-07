# Private Full-Migration Package Contract

The migration package contains real private health data and MUST never be committed, uploaded as a GitHub artifact, pasted into public logs, or stored outside the active migration runtime/approved private storage.

## Files

A package contains:

- `manifest.json`
- `domains.jsonl`
- `analytes.jsonl`
- `records.jsonl`
- `record_domains.jsonl`
- `sources.jsonl`
- `source_locations.jsonl`
- `record_sources.jsonl`
- `cases.jsonl`
- `case_links.jsonl`
- `labs.jsonl`
- `medications.jsonl`
- `monitoring.jsonl`
- `plan_items.jsonl`
- `questions.jsonl`
- `id_reservations.jsonl`

Each JSONL row is already transformed into the target HEALTH field names according to `docs/MIGRATION_FIELD_MAP.md` and `docs/MIGRATION_EDGE_CASES.md`. Missing values are JSON `null`; empty strings remain empty strings when the source explicitly contains an empty value.

## Initial manifest

Before sealing:

```json
{
  "schema_version": 1,
  "status": "CAPTURED",
  "captured_at": "<UTC ISO timestamp>",
  "old_healthdb_validation_pass": true,
  "old_healthdb_freeze_operation_id": "<UUID of old HealthDB PREPARED freeze operation>",
  "old_healthdb_freeze_state": "PREPARED",
  "old_healthdb_other_unfinished_operations": 0,
  "historical_sources_manifest_sha256": "<64 hex>",
  "tables": {}
}
```

The extractor must capture the Registry and record/source evidence under one migration freeze and must recompute all values from the live Drive-native HealthDB. Planning/MVP counts are forbidden as snapshot inputs.

The freeze is a dedicated old-HealthDB maintenance Change Log row in state `PREPARED`. The freeze row itself is not counted by `old_healthdb_other_unfinished_operations`; that field must be exactly `0`. The package records the freeze operation ID and `PREPARED` state so a sealed package cannot represent an unfrozen capture.

Immediately before the target HEALTH commit, the operator must reread the old Drive-native Change Log and prove that the same freeze operation is still `PREPARED` and is the sole unfinished old-HealthDB operation. If that check fails, the staged package is stale and must not be committed.

## Seal and verify

```bash
python scripts/migration/full_migration.py seal <private-package>
python scripts/migration/full_migration.py verify <private-package>
```

`seal` writes, for each table:

- file name
- exact row count
- SHA-256 of the JSONL file
- order-independent SHA-256 of canonical target rows

It also writes a package fingerprint that binds both:

- every canonical table fingerprint;
- the capture control metadata: schema/status, capture timestamp, old-HealthDB validation PASS, freeze operation ID/state, zero other unfinished operations, and the historical Sources manifest SHA-256.

Changing either medical content or freeze/capture control metadata after sealing invalidates the package.

`verify` is fail-closed and checks referential/domain invariants, ID ledger exactness, case lifecycle shape, literal Labs, source PRIMARY shape, removal of MVP markers, the exact table set, all recorded hashes, and the sealed package fingerprint.

## Staging

With `SUPABASE_DB_URL` available only in private runtime:

```bash
python scripts/migration/full_migration.py stage <private-package>
```

This creates/replaces only `health_migration_stage`, loads the complete package, and requires exact SHA-256 fingerprint equality between staging and the sealed package.

No public medical-domain row is modified by `stage`.

## Commit

Commit is deliberately impossible without both:

- a HEALTH operation already in `PREPARED`;
- the literal owner-authorization token `FULL_MIGRATION_AUTHORIZED`.

```bash
python scripts/migration/full_migration.py commit <private-package> \
  --operation-id <uuid> \
  --authorization FULL_MIGRATION_AUTHORIZED
```

The commit:

1. re-verifies the private package;
2. re-verifies exact staging fingerprints;
3. rejects any competing unfinished HEALTH operation;
4. replaces the medical-domain tables in one PostgreSQL transaction;
5. writes private snapshot counts/fingerprints into `system_state/full_migration_snapshot`;
6. stores the source freeze operation ID/state and control metadata in `system_state/full_migration_snapshot`;
7. advances only the supplied operation to `COMMITTED_REGISTRY`.

It does **not** set VALIDATED or FINALIZED.

## Mandatory post-commit gate

After commit:

```bash
python scripts/migration/full_migration.py compare <private-package> --schema public
```

This must PASS for every table. Then run the SQL validation suite, browser/security checks, source/backup verification and impacted OPERATION_AUDIT checks. Only after all of them PASS may the operation advance to VALIDATED/FINALIZED.

Do not remove staging until final validation is complete.

## Rollback before cutover

The old Drive-native HealthDB remains canonical. A failed migration is recovered by rebuilding/recommitting the new HEALTH target from the same sealed snapshot or a newer fresh snapshot. The old Drive source is never modified to roll back the new target.
