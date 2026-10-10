# AI Write audit clarifications

Status: documentation only, 2026-10-10. No writer or schema implementation is authorized.

| Finding | Proportionate decision |
| --- | --- |
| AW-01 | Originals receive distinct object IDs and are never overwritten by routine writing. Recheck real bytes, hash and object version before publication. Restrict later edits where possible; document residual risk and verify by later backup/integrity checks. |
| AW-02 | Bind each operation to a trusted immutable routine/migration class, authorized writer and scope. AI cannot select that class or finalize foreign operations. Existing free-text operation/mode alone is insufficient. |
| AW-03 | Bind semantic approval to an exact proposed-change fingerprint and expected versions of **all affected rows**; recheck them in the final transaction. No per-rule dependency engine for 37 legacy checks. |
| AW-04 | Atomic SQL COMMIT protects a single query snapshot, not several independent PWA requests. Temporary mixed versions on a composite screen are acceptable; do not claim cross-request atomicity. |
| AW-05 | Persist upload intent and correlation marker **before** provider call. Resolve timeout through marker, object identity and bytes; SHA alone is not identity. Ambiguity blocks publication. |
| AW-06 | One interaction question per new active medication intake event and check kind, with medication and REC links. Two new medications in one REC require two questions; retry adds none; genuinely new intake after prior closure adds one. |
| AW-07 | Lost COMMIT acknowledgement is UNKNOWN, not FAILED. Reconcile existing operation/key before retry or writer-slot release. |

All are future acceptance requirements, not proof of implemented protection. Full migration, backup, Scheduler and current Drive clinical writing are unchanged.
