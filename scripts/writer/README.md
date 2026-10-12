# Writer components and disabled canonical integration candidate

The canonical runtime is now installed in production in the disabled state.
Current private chat operation, authorization, historical exception and recovery
boundaries are described in [Writer operation](../../docs/WRITER_OPERATOR.md).
The dated component results below remain bound to their original inputs; they
do not describe the current deployment or authorize a medical operation.

The original fixture modules contain a TEST-only typed delta engine and reproducible synthetic checks. `build_standby.py` separately renders a disabled canonical integration candidate; it does not connect, deploy, enable Writer or authorize a clinical operation. Component approval and semantic receipt inputs are simulated by the administrator only. Clinical acceptance is separate from test mechanics.

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

## Durable preparation overlay and Source saga — 2026-10-12

`durable_runtime.sql` is an optional overlay on a new constrained synthetic
fixture. It adds caller-bound intents, a protected routine operation class,
durable PREPARED, serialized 1..999 allocation, retired-number preservation,
atomic reservation-to-used publication, 30 operation-bound component validation
rows, and restricted status/abandon entrypoints. It revokes the legacy direct
publication entrypoint from the fixture writer role. This is not a canonical
schema migration and does not alter `health_test_writer.v2_*`.

`test_durable.py` covers 33 local restricted TCP assertions, including foreign
caller denial, competing preparation, CREATE, rollback, revocation/expiry,
intent mutation, migration-class rejection and allocator exhaustion. Exact
candidate/intent approvals and semantic receipts remain administrator
simulations; this is not a verified owner approval service. The validation
journal does not replace the canonical validation catalog or 37-rule acceptance.

```sh
python scripts/writer/test_durable.py --docker-container <disposable-name> --out /private/durable.json
python scripts/writer/test_source_saga.py --out /private/source-saga.json
```

`source_saga.py` persists a correlation marker in a SQLite FULL/WAL journal
before creating a new local-provider object. Reconciliation binds marker,
provider identity, stable logical Source ID, actual SHA/length, operation and
candidate. Sixteen tests use actual synthetic bytes, including a created object
whose adapter drops the reply, journal reopening, replay, partial bytes,
ambiguous equal-hash objects, orphan preservation and later byte mutation.
This local provider is disposable; production Drive ACLs, an independent
verifier identity, SQL Source integration and PRIMARY rebind are not accepted.

The existing code-validation workflow can run an owner-dispatched two-phase
Supabase TEST probe against one administrator-created private fixture. Prepare
and publish are separate actual network runs, pinned to the exact workflow/code
SHA. Only the existing restricted TEST DB secret is used; no DDL or approval
changes are available to the probe. The administrator stages synthetic approvals
between runs. A successful remote run is separate evidence, never inferred
from the local result. The fixture schema must be readback-checked and removed
after the probe. Production enablement remains false.

Private SECURITY DEFINER entrypoints revoke PUBLIC execute and pin search_path;
only the bounded writer role receives execute. Design references:
[Supabase database functions](https://supabase.com/docs/guides/database/functions),
[RLS guidance](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Persistent SQL resumable journal and canonical standby candidate

`PostgresUploadJournal` uses the worker's persistent Session connection and
bounded SECURITY DEFINER routines. It journals the Source and session before
uploading bytes, validates caller/operation/folder/hash/length, serializes worker
ownership and resumes the same Google object after restart or acknowledgement
loss. Session URIs are private capability material. Revocation is checked before
every external upload request. Recording an already returned provider outcome
does not approve Source publication. SQLite fault tests remain separate evidence.

`SourceDriveProvider` allows create-only binary Source uploads into an explicitly
registered owner folder, with a separate read-only Google identity for byte
verification. File replacement, original purge and unbounded inventory methods
are disabled. SQL session key `63741020261013` coordinates it with the complete
backup's shared capture lock across both repositories.

`build_standby.py` routes clinical references into `public` and keeps controls
in private `health_writer`. The candidate installs disabled. Executor,
authorization and verifier groups have separate bounded routines, no direct
clinical/control DML, and no helper access. Intents bind an immutable chat command
digest and conversation reference. A proposal computes an exact after-state in
a rolled-back subtransaction; inserts require explicit values for all columns
so planning consumes no sequence/default-clock effects. Clinical triggers cause
the operation to stop until individually reviewed.

Publication requires independent literal evidence for changed lab rows; it
preserves unchanged historical rows without reusing a historical semantic PASS.
Ten semantic receipts remain mandatory for the exact candidate and after-state.
New namespaced `WRITER_V1_RULE_01..37` results preserve the existing canonical
registry. Rule 13 is explicitly SKIP for plain SQL body_text operations; this
does not assert successful Markdown renderer testing. Code, migration and
primary folder bindings are checked before mutation. No migration rerun or
physical original/archive purge is exposed.

Local restricted TCP tests and actual disposable Google/SQL transport recovery
are separate evidence. The standby suite's approval/semantic inputs are
synthetic; a green suite alone never declares clinical or production readiness.
Canonical Source locations use the existing `google-drive` / `HEALTH_PRIMARY`
provider/account identifiers. The renderer replaces the prototype account-name
validator with that exact account; new publication cannot introduce the TEST
alias `primary`. The actual disposable Google/SQL recovery test was repeated
against this aligned renderer and passed 46 assertions; approvals and clinical
semantic inputs in that test remain explicitly synthetic. An independent
read-only check of the existing canonical Source graph also read and verified
all 26 registered original objects (60,806,209 bytes) with the newly authorized
Reader account; it made no Source or clinical mutations.
The owner-approved legacy date/ID policy is a one-row, whole-row SHA binding in
private legacy_record_exceptions. The global schema check remains strict for all
other rows and all other fields. Changing any part of the historical row,
removing it, fixing its date, or disabling the exception stops publication. Rule
11's current operation audit explicitly includes the bound exception and owner
decision. No ordinary Writer or verifier can register or rebind an exception.

Private request_context and review_candidate routines expose an owned approved
intent's context and a separate verifier's exact before/after projection. Row
hashes are computed by PostgreSQL; callers never need a general SQL/hash helper.
SourceUploader carries only the owner upload credential and cannot claim an
independent readback. The separate verifier reads provider bytes and records the
exact Source/candidate evidence. chat_worker.py sends only opaque request UUIDs
and SHA-256 to the owner-dispatched authorization workflow; medical changes and
review evidence remain in protected local files. It never synthesizes semantic
PASS receipts. The new signed broker pins project, actor, repository, workflow,
branch, commit and audience, including the current immutable GitHub subject form.

Production migration 20261012200609_health_writer_standby_v1.sql is staged with
the exact owner-approved legacy baseline guard, runtime disabled, no credential
or private Drive-folder configuration, and no clinical data rewrite. Installation,
real Supabase network acceptance and enabling are separate recorded steps.
