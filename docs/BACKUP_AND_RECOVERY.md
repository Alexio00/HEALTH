# Complete backup and recovery

The accepted private scheduler produces one coherent complete archive containing
all captured PostgreSQL schemas and tables, Auth data, portable roles/settings
and memberships, migration history, the complete primary Source corpus, Source
identity/locator bindings, frozen original lineage and checksums. Capture uses
the restricted read-only backup role and the same exclusion boundary as Writer.
Private Auth/session data makes the whole archive sensitive; no payload belongs
in public logs or GitHub artifacts.

Each daily run uploads a candidate to the independent owner's private Drive,
downloads the entire archive, checks every member and Source byte/graph binding,
restores the database and roles in isolation, and exercises the restored Auth
HTTP lifecycle. It promotes the verified new archive before moving the exact
previous active set to Drive Trash. An upload or verification failure preserves
the previous active backup. There is one active set; trashed archives consume
capacity until provider expiry. No permanent-delete or empty-Trash operation is
used. The owner's future-capacity assumption is explicit and quota is not queried.

The schedule targets 03:00 Europe/Moscow (00:00 UTC). GitHub delivery can be
delayed. The accepted executor commit and enabled flag gate the replacement daily
pipeline; private operational evidence identifies actual activation. Historical
CLI/public-only backups and B-04 migration finalization remain earlier scopes,
not the current complete archive format or a reason to rerun migration.

Full provider recreation and independent full-byte verification of a replacement
Source root are exercised at backup activation. Daily verification restores and
checks archived Source bytes/graph, but does not recreate the entire cloud Source
corpus each day. Changed recovery executors require renewed full acceptance.
Source IDs and medical identities survive physical provider locator changes.

Recovery first verifies the exact captured table and role fingerprints. It then
deliberately disables Writer, clears its code pin and disables upload folders.
Pending operations, NNN reservations, authorizations, reviews, audit rows and
resumable session references remain preserved. Recovery never automatically
resumes publishing or pending external uploads. A verified recreated Source root,
current accepted code and pending-operation reconciliation precede a separately
accepted reactivation. See [Writer operation](WRITER_OPERATOR.md) and
[Auth recovery](AUTH_RECOVERY.md).

The private operational contract is
[SHEDULLER complete backup pipeline](https://github.com/Alexio000/SHEDULLER/blob/main/docs/COMPLETE_BACKUP_PIPELINE.md).
Historical migration recovery evidence remains in the private
[B-04/A-05 guide](https://github.com/Alexio000/SHEDULLER/blob/main/docs/AUDIT_B04_A05_RECOVERY.md).
Neither an old PASS nor a synthetic recovery is evidence for a new live archive.
Current run/head, authenticated artifact digest, archive round trip, actual
isolated restore and final cloud rotation readback must be verified together.

Old projects, legacy Registry/REC Docs and original sources remain preserved
until a separate owner disposal decision. Backup rotation never authorizes
deletion of those originals.
