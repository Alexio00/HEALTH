# Session pooler runtime policy — owner approved 2026-10-12

The owner selected the earlier Docker Session-pooler connection mechanism for
the new Writer and backup. Use the project-bound restricted Writer role on port
5432 with `verify-full`, the pinned CA, and a temporary 0600 passfile.
The CA secret is `HEALTH_SUPABASE_CA_PEM`; missing/changed certificates fail
closed. Database owner and service-role credentials must not reach the Writer.

The bounded TEST TLS dispatch proves real client certificate/name verification
for the existing `health_test_ci` role. It runs no clinical SQL and requires the
exact reviewed branch/SHA and owner dispatch. Durable prepare/publish now use
the same verified transport, rather than an environment PGPASSWORD plus require.
Static self-tests of earlier URL shapes are not live connection acceptance.

Read-only diagnostics explicitly start `BEGIN READ ONLY`; startup options alone
are insufficient to establish the observed transaction state behind a pooler.
Client-to-pooler TLS and the PostgreSQL backend leg remain separately reported.
The owner accepted this boundary; it does not imply backend TLS was observed.

This is transport preparation, not production Writer deployment or canonical
cutover. Signed authorization, semantic validation, Source provider and full
backup/restore acceptance retain their own concrete implementation checks.
