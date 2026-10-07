# Database validation coverage

The live database is validated through executable SQL under `scripts/validation/` plus PostgreSQL constraints/indexes.

Covered invariants include:

- one unfinished write operation maximum;
- record ID/NNN/ledger consistency;
- case OPEN/CLOSES cardinality and closing-record shape;
- Labs referential integrity and exact-duplicate prevention;
- literal laboratory value/reference preservation marker during migration;
- provider-neutral source identity/location model;
- RLS on every public table;
- anonymous browser denial;
- authenticated SELECT allow-list and write denial;
- exact browser policy shape;
- technical-table isolation;
- safe future default privileges;
- no public SECURITY DEFINER function or unreviewed public view;
- full-migration snapshot/fingerprint requirements.

Migration-package logic additionally has a synthetic CI self-test.
