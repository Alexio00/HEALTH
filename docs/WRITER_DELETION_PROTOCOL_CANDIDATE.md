# Deletion and corrections — implementation candidate

Status: DRAFT / partial synthetic implementation / owner semantics pending.

| Request | Candidate behavior | Required acceptance |
| --- | --- | --- |
| Correct REC text | Row compare-and-set; retain full prior row in operation audit | Owner approval of exact correction; immutable production revision history and retrieval |
| Cancel REC | `status=cancelled`; keep record identity, NNN ledger and provenance | Explicit downstream effect on Cases/Labs/current-state and display decided by owner |
| Remove wrong derived question/lab/link | Typed DELETE in the same operation; preserve REC/original and audit prior derivative | Exact source/owner basis, dependency refresh and case/lab/current-state validation |
| Stop active medication | Status transition derived from evidence/owner decision | Never infer completion from silence; interaction-question lifecycle checked |
| Delete REC physically | Rejected by this candidate | Separate purge design, impact manifest, retention obligations and explicit approval |
| Delete/overwrite Source original | Rejected by this candidate | Reference graph, legal/owner retention, independent backup, provider permissions and separate purge authorization |
| Replace PRIMARY storage | Separate verified rebind; not implemented here | Actual byte readback, immutable Source ID, backup independence, A-05 and recovery proof |
| Delete old Drive project/archive | Outside this candidate | Accepted cutover, empty delta, applicable old Validation and separate archive/deletion authorization |

The candidate demonstrates transactional derivative deletion and REC soft cancellation. It does not silently cascade from an annulled REC or delete original files. Production policy must specify whether derived entries are retracted, superseded or retained and how historical views show them. A clinical validator must approve that exact resulting state before publication.

Every permitted removal must list affected REC/derivatives/source links, show a before/after candidate, bind owner approval to its digest, refresh dependent semantic evidence and retain an immutable operation/revision receipt. Source physical purge must remain a separate protocol with explicit object identifiers and proof that the relevant originals and recovery obligations are satisfied.
