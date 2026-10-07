# Integration / acceptance tests

Implemented evidence includes:

- authenticated read-only browser path;
- anonymous denial and browser write denial;
- Source opening;
- REC rendering from PostgreSQL;
- representative migrated relations;
- independent backup/readback;
- isolated MVP restore;
- scheduler database -> Sources -> verification chain;
- synthetic full-migration package seal/verify CI test.

Before full migration:
- hardened scheduler workflow must pass after tooling changes;
- owner must complete the account-level gates recorded in Project State.

After full migration:
- exact private-package -> public table fingerprint comparison;
- full invariant suite;
- full backup round-trip and isolated restore drill;
- owner read-only PWA smoke check.
