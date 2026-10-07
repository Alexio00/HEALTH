# Migration tooling

Full migration is executable and fail-closed.

- `full_migration.py` — seals and verifies a private snapshot package, loads an isolated staging schema, performs exact table fingerprints, and performs a guarded transactional commit only after explicit owner authorization.
- `PACKAGE_CONTRACT.md` — private runtime package format and execution sequence.

The code contains no real medical data. Snapshot packages are private runtime material and must never be committed or uploaded as CI artifacts.

The active Drive-native HealthDB remains canonical until explicit cutover.
