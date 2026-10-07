# Validation tooling

Validation is fail-closed and public-safe.

Executable validators:

- `auth_invariants.sql` — single-owner Auth/database binding invariants;
- `security_invariants.sql` — RLS, policy shape, browser grants, technical-table isolation, public view/function and default-privilege checks;
- `full_migration_invariants.sql` — post-load snapshot/count/structural migration checks;
- `public_secret_guard.py` — scans the public repository for secret-like values without flagging ordinary field names.

Exact old-to-new full-migration fidelity is independently proven by canonical table fingerprints in `scripts/migration/full_migration.py`. Counts alone are never accepted as full-migration fidelity.
