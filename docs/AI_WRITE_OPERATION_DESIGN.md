# Routine AI write: state machine and recovery contract

Status: DESIGN ONLY / NOT IMPLEMENTED / NOT PRODUCTION AUTHORIZATION
Date: 2026-10-10

This contract applies to future routine ChatGPT/AI writes after an independently approved HEALTH cutover. The currently canonical Drive-native HealthDB remains unchanged; its live Google Drive Project Manual and Project State govern current owner-authorized edits. The full migration executor, its separately staged COMMITTED_REGISTRY, B-04 finalization, A-05 recovery and old-Drive freeze are explicitly out of scope. Neither a Health API nor restricted PostgreSQL RPC is now being developed or selected.

## Architectural decisions

| ID | Decision | Consequence |
| --- | --- | --- |
| WD-01 | Ordinary medical changes are **atomically published**: rows, derived links, required validation stamps, NNN reserved-to-used and FINALIZED commit in **one SQL transaction**. | One SQL query sees one consistent committed snapshot; separate PWA requests may briefly display mixed versions across COMMIT. |
| WD-02 | PREPARED is durable during preparation. Inside the final publish transaction, progress through COMMITTED_REGISTRY and VALIDATED to FINALIZED in order; only FINALIZED is externally committed. | Do not reinterpret the special persistent COMMITTED_REGISTRY of full migration. |
| WD-03 | An approved, limited writer must enforce operation ownership for **all** medical DML. | operations_single_writer_idx blocks competing active rows, but alone does not block privileged direct table updates. |
| WD-04 | A private unique idempotency key binds owner approval, requested change, scope and operation UUID. | Repeated requests or timeout retries must not create duplicate REC/Source. |
| WD-05 | Versioned compare-and-set on existing REC and related rows, plus immutable old-version evidence. | Stale AI decisions fail closed; silent overwrites are forbidden. |
| WD-06 | Only actually durably reserved NNN are retired on abandonment, never reused. | A transaction rolled back before reservation is **not** a used or retired ID. |
| WD-07 | Original Sources are verified before publish; independent backup is a later separate checkpoint. | No invented Source SHA/PRIMARY/BACKUP locator and no SQL-to-Drive atomicity claim. |
| WD-08 | Semantic and owner checks pass before publication. Structural and snapshot-freshness checks rerun within the short final transaction. | No delayed semantic PASS can authorize already-visible, unreviewed medical data. |
| WD-09 | FAILED can release the slot only when **no** medical publication happened and reserved ID / external artifacts are accounted for. | Unknown commit result remains BLOCKED; FINALIZED is never retrospectively rewritten to FAILED. |

These are acceptance targets, **not deployed capabilities**. Existing SQL has a partial unique operations index and id_reservations, but not a verified routine writer, durable idempotency/revision journal or all permission controls.

## Required routine state transitions

| Transition | Authority/precondition | Durable action | Failure behavior |
| --- | --- | --- | --- |
| None -> PREPARED | Explicit owner command, verified caller/scope/idempotency; active-index slot available | Operation ID/approval scope saved; no medical rows changed | Competing writer denied without touching its operation |
| PREPARED -> PREPARED | Same operation owner | Prepare candidate, reserve new NNN if needed, verify Sources, owner decisions and semantic evidence | Recover/retry same operation; do not publish |
| PREPARED -> COMMITTED_REGISTRY | Final SQL transaction only; candidate, Source and approval fingerprint match | Uncommitted medical DML including all derived rows | Exception rolls entire final transaction back |
| COMMITTED_REGISTRY -> VALIDATED | Same SQL transaction; operation/dependency-fresh checks PASS | Uncommitted validation stamps | Missing, FAIL or SKIP prevents commit |
| VALIDATED -> FINALIZED | Same SQL transaction; final version checks, reserved NNN -> used, source proofs and audit PASS | Single commit publishes **all** medical rows and FINALIZED together | Entire transaction rolls back on error |
| PREPARED -> FAILED | Verified no publication; staged files and NNN reconciled | Failure reason and artifacts recorded, allocated NNN retired if applicable | Uncertain status must stay blocked |
| FINALIZED -> anything | Not allowed | New correction uses new operation referencing original | Never erase previous success |
| Any other state movement | Not allowed for routine writer | Reject and audit | Do not mutate operation to bypass lock |

The required state chain is logical; COMMITTED_REGISTRY/VALIDATED need not be separately committed in routine writes. The existing **one-time full migration** has a different audited recovery contract, intentionally retaining COMMITTED_REGISTRY while waiting for B-04. The future implementation must distinguish operation type and cannot mix these workflows. The routine writer must check a protected operation class and owner binding before advancing its own operation. Free-text mode alone is not sufficient.

## Algorithm

1. Interpret owner intent without writing. Differentiate discussion/read-only, explicit import, and technical maintenance. An attachment alone is not an import command.
2. Validate authorization and the expected change set, including explicit OPEN/CLOSES decisions, provenance and exact literal laboratory data. Record private approval reference and request fingerprint, never raw medical content in public GitHub.
3. Claim PREPARED through an atomic DB insert. If another active row exists, reject with no clinical or Source mutation; never mark the competing writer FAILED.
4. For new REC only, serialize NNN allocation using the live ledger; choose a number beyond all durable used/retired/reserved allocations in range 1..999. Persist reserved with current operation ownership. If exhausted, stop.
5. Materialize any new original privately on new HEALTH/Sources, recompute SHA-256 and size from actual bytes, read back, verify PRIMARY; keep durable candidate ID/locator/hash and retry key. Do not fabricate an original for owner-statement REC or label a never-backed-up object BACKUP.
6. Build complete before/after candidate: records.body_text, domains, sources, cases, labs, medications, monitoring, plan, questions and related evidence. Preserve original precision and absence/null/negative distinctions. Semantic audits and owner approvals apply to the exact candidate fingerprint.
7. Within one short SQL transaction, lock and recheck operation ownership, permission/approval fingerprint, duplicate key and row revisions; apply every linked medical DML change, reservation used, machine checks, current semantic stamps, transitions to FINALIZED, and durable before/after audit. Commit once; no provisional medical rows are externally visible.
8. Read back operation and affected records. If response is lost, **reconcile the existing idempotency key and operation first**; never assume failure and allocate a fresh REC.
9. Return successful IDs and changed entities only after verified commit; reconcile staged/orphan files separately without deleting original evidence.

## Failure outcomes

| Failure | Published data | Required response |
| --- | --- | --- |
| No owner approval, ambiguous provenance/case | None | Clarify; do not start |
| Concurrent PREPARED | None | Reject loser, preserve winner |
| PREPARED crash before durable NNN | None | Same-operation recovery; no guessed retirement |
| Crash after durable reservation | None | Resume or retire NNN on safe abandonment |
| Source upload/readback failed | None | Keep private failure/orphan journal; block commit |
| Source success, SQL rollback | None | Preserve original; reconcile candidate; retire allocated NNN only if abandoning |
| Owner/REC revision stale | None | Roll back; obtain fresh approval as needed |
| Validation fails | None | Block final transaction; record negative evidence |
| SQL COMMIT acknowledgment lost | **Unknown** | Query operation/key and exact public rows before retry; don't mark FAILED |
| Successful FINALIZED, subsequent anomaly | All rows committed | New corrective operation and incident, never silent rollback |
| Backup failure after FINALIZED | Normal write still valid | Scheduler error/retry; separate backup incident |
| Recovery cannot prove transaction result | Unknown | Keep writer blocked, owner-controlled recovery; no time-based auto-unlock |

## Source and backup boundaries

A routine FINALIZED requires verified source PRIMARY objects referenced by the new record; it does not require fresh full-system recovery proof. Scheduler must produce a coherent PostgreSQL snapshot and a version-matched immutable Source manifest, never claim a mixed or partial inventory as a complete backup. Staged but unpublished files must not be presented as linked clinical originals. Independent backup failure is reported separately without retroactively deleting a finished medical edit. Full-migration B-04/A-05 remain separate requirements.

## Permission boundary

- Owner authorizes intent; AI drafts/extracts and invokes an approved bounded interface.
- The future limited writer owns SQL transaction and source publication; no generic privileged SQL connector used by the AI for unrestricted medical DML.
- PWA stays SELECT-only; unapproved readers cannot access medical data.
- SHEDULLER does read-only backup/verification, not routine clinical writes.
- Full migration executor and recovery authority are separate, tightly gated trust classes.

## Source and operation audit clarifications

For new Sources: persist an upload correlation marker before the external call, use a new object instead of overwriting a linked original, and reconcile a lost response by marker, object identity and actual bytes. Hash equality alone is not object identity; ambiguous matches stop the write. Verify bytes and metadata before publication. Restrict external changes when possible; later changes remain a residual risk checked by integrity verification and backup.

**Operation class (AW-02):** the trusted routine writer binds a protected operation class, owner/caller identity and scope to its own operation ID. The AI cannot supply or change that class; a routine writer refuses migration-class and foreign IDs. Existing free-text operation and mode fields do not establish this boundary by themselves.

**Validation freshness (AW-03):** bind approval and relevant semantic results to one proposed-change fingerprint and expected versions of every affected record/dependency. Recheck those versions inside the final transaction. No independent dependency-version mechanism for all 37 legacy checks is required now.

**AW-06:** the interaction-check question uses a stable new-medication intake event ID and check kind, not only the prescribing REC. Separate events under the same REC yield separate questions; retries of one event do not duplicate it. Later new intake after closure requires a new event. Implementation is deferred.

## Not yet implemented

The durable idempotency/approval journal, immutable revision history, atomic NNN allocator, verified Source saga, restricted trusted entrypoint, operation-scoped clinical validation and coherent incremental backup checkpoint must be designed and tested on synthetic fixtures before accepting any post-cutover writes. This document does not add SQL schema, functions, credentials or workflows.
