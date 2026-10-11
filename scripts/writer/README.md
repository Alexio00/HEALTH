# Isolated Writer component candidate

This directory contains a TEST-only typed delta engine and reproducible synthetic checks. It is not a production migration, a replacement for the existing `health_test_writer.v2_*` protocol, an owner approval service, or a medical verifier. No existing clinical rows are copied into the fixture. Approval and semantic receipt inputs are simulated by the administrator only.

## Verified component behavior

The 2026-10-11 PostgreSQL TEST run recorded 45/45 checks: 42 synthetic behavior/structure checks plus three catalog privilege assertions. All successful publications were rolled back after checking the audit, exact after-state and idempotent replay. The negative tests compare the unchanged medical-domain checkpoint after rollback. Catalog assertions do not prove actual network calls as `health_test_ci`; that acceptance is NOT_RUN for this component.

- Exact typed keys and row hashes; reject stale row/domain, unknown table/field and REC identity changes.
- Single-writer transaction, linked case closure, linked medication + interaction question, update and soft cancellation of REC.
- DELETE for selected derived rows with required basis, audit and downstream validation; physical REC/Source purge is blocked.
- Literal lab precision preserved; changing `1.230` into `1.23` without a separately verified expected source row is rejected.
- Fresh semantic/source receipts tied to candidate and after-state; missing, expired or mismatched evidence blocks publication. Synthetic receipts do not establish real semantics.
- Before/after snapshots are private fixture history. Production retention/storage cost, immutable audit ownership and revision retrieval are not accepted by this experiment.

## Reproduce

Use a disposable PostgreSQL TEST environment with the existing HEALTH writer role names. `catalog_v1.json` contains only the 16 allowlisted tables' typed schema metadata from the reviewed TEST run. Confirm that catalog against the intended TEST version; do not export rows, credentials or medical files. Catalog types/defaults are trusted administrator input, not a remote caller payload.

```sh
python scripts/writer/build_fixture.py --schema health_writer_fixture_<unique_suffix> --catalog scripts/writer/catalog_v1.json --out /private/fixture.sql
```

Review the rendered SQL, confirm TEST project identity, and apply it as a TEST administrator. Render `__SCHEMA__` in both test files to the same schema. Run `synthetic_tests.sql` and then `supplemental_tests.sql` in one administrative session and read `writer_test_results`. Do not run the publication engine against production.

The clinical fixture tables deliberately omit most original PK/FK/check constraints so corruptions can reach the structural validator; the single-writer index and receipt parent FK are present. This is a component test, not full schema parity. The fixtures do not implement the existing allocator, retired-number retry protocol, upload saga, uncertain network COMMIT reconciliation, or provider Source byte verification.

After recording the synthetic results, remove only the newly created schema, first confirming its unique name and schema comment `HEALTH_SYNTHETIC_WRITER_FIXTURE_V1`. The review run cleaned its fixture. No PUBLIC grants or existing TEST role memberships were changed.

## Local TCP and production-constraint component acceptance

`test_network.py` repeats the 45 synthetic checks plus the retired/used NNN
regression, then builds a second disposable fixture with 62 reviewed production
PK/FK/CHECK/UNIQUE constraints and 17 non-constraint indexes from
`constraints_v1.json` (production read-only catalog, 2026-10-11). This narrows the
constraint-parity gap; production RLS policies, trigger behavior, Auth and v2
integration are not reproduced or accepted by this harness.

The harness creates a unique synthetic SCRAM login with only the fixture Writer
role, authenticates via TCP, and asserts exact SQLSTATE `42501` for 11 privileged
actions, including direct clinical DML, self-approval, receipt/audit tampering,
helper calls and role escalation. It also tests actual publication and audit,
expiry/revocation/tampering, transaction rollback, missing receipt, concurrent
stale writers, dependency mutation and replay digest conflict. The new
`status(text)` returns only operation/digest metadata to reconcile an uncertain
client acknowledgement. Acknowledgement loss is simulated; this is not a
network-disconnect fault injection test.

The local 2026-10-11 run passed all 30 component assertions (including the prior
45-check suite and catalog reproduction). Approval and source receipts remain
administrator simulations. This is local PostgreSQL TCP evidence, not actual
Supabase restricted-role network or clinical acceptance. The original catalog
assertions retain their original meaning; this harness adds separate evidence.

```sh
# Disposable PostgreSQL 17 on 127.0.0.1:5432, synthetic postgres administrator.
PGPASSWORD=health-synthetic python scripts/writer/test_network.py --out /tmp/writer.json
# Or a disposable local container; no host ports or external network required.
python scripts/writer/test_network.py --docker-container <disposable-name> --out /private/writer.json
```

Only run against a disposable database. The harness creates role names used by
the fixture and grants the synthetic `health_test_ci` role its fixture membership.
Both uniquely named schemas and the uniquely named login are removed and
readback-verified; the disposable server's shared no-login fixture roles remain.

## Production integration prerequisites

1. Review and integrate the 20 structural prototypes with real HEALTH constraints, `validation_checks`/`validation_results`, allocator and immutable revision audit. Current rule-number correspondence is partial component coverage; see `RULE_APPLICABILITY.md`.
2. Replace simulated candidate approval with the exact owner approval verifier, including actor/workflow/code pins, approval expiry and revocation. Do not use administrator/service-role credentials as the normal ChatGPT writer.
3. Provide an independent Source verifier that reads actual bytes and signs/binds hash, length, Source ID and location; implement recoverable upload/rebind transitions before exposing them.
4. Run all required clinical/semantic cases and 37-rule applicability acceptance. Historical migration stamps and prior fixed-candidate OIDC success are not acceptance for this new engine.
5. Prove actual restricted network positive + exact permission-denied negative tests, including unconfirmed COMMIT/status reconciliation, replay conflict and concurrent writers.
6. Accept the backup/recovery boundary and deletion protocol separately. Production enablement requires the accepted cutover mandate and approval for the concrete candidate.
