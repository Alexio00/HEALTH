# HEALTH work evidence — 2026-10-11

Status: reviewed-component candidate; production/cutover readiness remains NO-GO.
This is fresh executor observation, not an independent acceptance audit.

## Exact target and baseline

Target UUID `fa39e51f-3d95-4f82-bd3b-94438e7139a1`; package fingerprint
`b424684d5cbf9a4a38a1174a294e762f1548be5a072073c686d6bf9d5c8e538f`.
Live target: FINALIZED/PASS at `2026-10-11T08:09:06.67552Z`; unfinished=0.
Fresh full-migration invariants: 27/27 PASS. Security/Auth invariant scripts:
PASS in READ ONLY transactions. FK covering-index gaps: 0. No production DML.

Fresh connected Drive reads matched all 13 frozen Registry tabs. 1729 typed
DATE cells required the same serial-to-date interpretation as the original
XLSX capture; other cell strings were compared exactly. All 22 native REC
document text hashes matched the frozen capture (text export BOM removed and
universal newline handling as in the original `read_text`). Live Validation:
37/37 PASS. MAINT-011 remains the only unfinished Drive maintenance, PREPARED.
Complete live original-byte/tree zero delta is still NOT_RUN.

Current owner mandate: direct instruction to execute the owner-authorized
handoff. It authorizes continued work and candidate preparation/update, without
backdating permission or authorizing canonical cutover/release of the freeze.
Original actor/code/TLS/approval history for the prior FINALIZED update remains
unestablished. 22 target audit stamps reference acceptance receipt
`e9ca9e7d44004be32ffb32392e94dc9efd372db1969ac1ec95becc0383c0482c`;
that exact original was not found in 92 tested JSON files in three prior working
boundaries. Eight audit results and two formula rows have no target-bound PASS
entry; new read-only checks do not silently mint their historical stamps.

## Recovery and original-identity reconciliation

Authenticated GitHub run `38128250983`, attempt 1, producer
`2d994caba056f11aa50618fc145ee1d3d95ca4fa`: SUCCESS.
Artifact ID `11698183229`, digest
`5645f53b15ee6e8918c9cea6e5039783ef245e36fd1e9b6be001ca9341990ce7`;
the sole attestation binds private proof
`a1912e8a466f6a0285f6d0c8612cd4d9bfcf167e5682540d54c471f9af55a566`.
Snapshot `2026-10-11T08-36-00Z`: private proof/MANIFEST/Source manifest/sidecar
bindings verified, five dumps hash/read-checked, physical migration ledger
11/11, all 15 actual live/backup/restored fingerprints equal. Actual bytes of
all 267 corpus objects were read and SHA/length verified. These are separate
authenticated/run, offline-binding and actual-readback observations.

`272 - 267 = 5 unlinked originals` is not a valid identity reconciliation:
two of the 26 linked Sources are also among 241 Historical originals. Mapping
the live `sources.metadata.legacy_drive_object_id` to the frozen inventory
shows 265 unique original identities in the corpus and **seven** unlinked
duplicates. All seven SHA/length pairs are present in the byte-verified corpus;
their seven original Drive IDs and sizes were freshly read through the connected
Drive account. Separate backup paths/old identities could not be uniquely bound
to the current independent inventory. Full restoration of all 272 original
identities is NOT_RUN; this is neither evidence of byte loss nor a full-identity
restore PASS. No original or duplicate was deleted.

The live recovery pointer was not changed and still references run
`38076521113`, snapshot `2026-10-10T17-52-54Z`.

## Operational boundary

SHEDULLER is a private personal repository owned by Alexio000, with admin access
available to the authenticated owner account. Repository secrets include
`SUPABASE_DB_URL` and `RCLONE_CONFIG`; environment inventory is empty.
Secret values were not retrieved into the chat or local reports. Fresh owner-
dispatched read-only Actions inventory run `38167449902`, attempt 1, exact
SHEDULLER candidate `4af32f0025bd9700296bf611a0b00c8b18115e96` passed. Its actual
DB URL authenticates as `postgres`: BYPASSRLS, CREATE ROLE/DB, ownership and
INSERT/UPDATE/DELETE/TRUNCATE on all eleven inspected clinical/control tables,
including `operations`. Client TLSv1.3 is observed in the same psql session;
configured sslmode is `require`, not verify-full. The pooler/database leg's
pg_stat_ssl=false is reported separately. This is not owner migration executor
TLS. Other equivalent credential scopes remain unestablished. Production
`health_backup_reader` is absent. The separate service_role catalog privileges
do not describe the actual Actions postgres role.

The local secured backup token has canDelete/canEdit/canShare=true on the new
exact corpus folder. Declared primary scope is drive.readonly; backup scope is
drive. The actual Actions token was also checked and has all four capabilities
on the exact verified recovery folder. C-M02 retention isolation is not
established. C-M01 transition remains open until a complete substitute backup,
restore/Auth/Source/schedule chain is demonstrated. Working credentials, schedules
and permissions were preserved.

The prior genuine owner-approved Windows offline execution packet
`20a40b66-e419-4a9d-9dcc-71008178aba2` was found: 40/40 recorded file hashes and
lengths matched; Verify, BuildCheck/check and runtime observations were PASS.
Current external bootstrap bytes remain SHA
`3caa5fb07bf5d752ec056693e0ff957208655d987ecfb3d2a1c2983fda73eb97`,
11447 bytes; all 18 pinned tools/plugins matched. A fresh external Verify passed
using SHEDULLER `303f2124d35f6bb5ffb6b4b5615f2412d076b4ea` and HEALTH
`f866d4370af67645e1a2758e5a12a3104494bfd3`. BuildCheck/check evidence is from
that prior actual run, not rerun or independent acceptance by this work.
Execute was not called; target already FINALIZED.

## Writer component change and evidence

Adds TEST-only `status(text)` exposing operation/digest metadata without clinical
snapshots. `build_fixture.py --constraints` optionally reproduces 62 production
PK/FK/CHECK/UNIQUE constraints and 17 non-constraint indexes from read-only catalog
metadata. The original unconstrained corruption fixture is kept separately;
RLS policies/triggers/Auth/v2 integration are not reproduced by the constrained
fixture. Neither fixture is a production deployment migration.

`test_network.py` runs the previous 45/45 checks and retired-number regression,
then authenticates a unique synthetic SCRAM login over actual TCP. The login has
only the Writer fixture membership, no superuser/bypassrls/role-creation access.
Eleven privileged DML/helper/self-approval/audit/escalation attempts are denied
with exact server SQLSTATE 42501. Positive publication/audit/status/replay,
expiry/revocation/tampering, rollback, missing receipts, parallel stale candidates
(exact P0001), dependency mutation and replay conflict passed. All 30 component
assertions passed. Candidate approval and semantic/source receipts are explicitly
administrator simulations. COMMIT acknowledgement loss is simulated, not network
fault injection. Actual Supabase restricted-role/clinical acceptance is NOT_RUN.
Both unique schemas and the unique login were removed and cleanup readback passed.

Code validation now runs these tests in a separate empty disposable database
and the 11 offline recovery-binding tests. Run `38166844907`, exact head
`4fed7602cb61c2503c5d07c9afee07e6456f1a07`: SUCCESS. Later head changes require
their own CI result; this PASS does not accept the general Writer.

## Remaining acceptance

1. Original referenced acceptance/execution receipts and exact execution pins;
   fresh evidence may be recorded without reconstructing a past owner signature.
2. Effective credential inventory and tested full backup replacement; independent
   enforceable retained boundary; actual accepted local executor TLS.
3. General Writer integration with real operation/revision/validation tables,
   allocator and retired-number recovery, exact-pinned OIDC candidate approval,
   Source byte verifier/upload saga, all applicable semantic proofs and actual
   Supabase restricted-role acceptance. The fixed-candidate Edge is not expanded.
4. Full original-identity recovery including the seven unlinked duplicates, A-05
   replacement PRIMARY/rebind, human real-original PWA acceptance and complete
   fresh DB+Source checkpoint/live source-tree delta.
5. Separate owner decision on the concrete canonical cutover/freeze release.

No cutover GO, merge/release/activation or archive/project purge is claimed.
