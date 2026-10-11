# Production acceptance work package

Status: evidence reconciliation and TEST component development; not production GO.

The full migration operation is already FINALIZED/PASS in the live target. This observation is not proof of the original executor, code/TLS boundary or owner approval. Do not rerun import/reset to reconcile missing receipts. `reconcile_finalization.sql` reads the exact observed operation, stamps and audit configuration without medical payloads.

## Required execution evidence

Collect the original execution receipt, independently retained owner finalization permission, exact HEALTH/SHEDULLER SHAs, image digest, trust bootstrap raw-byte digest, TLS observation and acceptance receipt referenced by the live stamps. Match times, operation UUID, package fingerprint and all proof file hashes. Record missing items as missing; do not reconstruct a past authorization from a later technical review.

`verify_recovery_artifact.py` checks a downloaded GitHub artifact against its independently fetched digest, and binds the contained attestation to the private restore proof, database MANIFEST, Source manifest and SOURCE-EVIDENCE sidecar. It is offline and read-only. Its PASS means digest/binding checks only. Actual live database fingerprints, Source byte readback, authenticated run metadata and owner approval remain independent checks. It never finalizes or changes the live recovery pointer.

## Operational gates

- C-M01: inventory effective Actions repository/organization/environment credential exposure and every equivalent deployment credential; provision and test an owner-controlled/restricted backup replacement before retiring the working backup path. A read-only database setting alone does not deny DML privileges. Full five-file restore including Auth/roles, schema/data and migration history is required for the replacement.
- C-M02: verify retention and ACL on an independent backup boundary. Demonstrate that the normal writer/backup automation cannot delete, overwrite, rename or share away the retained copy. A same-account remote with mutable token permissions and an immutable-upload flag does not establish this boundary.
- Bootstrap/TLS: independently retained reviewed bootstrap and exact host tool pins; clean reviewed checkouts; Verify then BuildCheck/check without production credentials. TLS must be proved on the actual approved executor and endpoint. A Session pooler proposal requires its separate accepted policy; the management audit connection does not establish local TLS.

## Cutover acceptance

Keep old Drive canonical and frozen while reconciling. Prepare actual A-05 replacement PRIMARY with byte manifests/readback and rebind recovery, user acceptance in the PWA of real originals and representative REC/current-state pages, a fresh coherent DB+Source backup and restore, zero old-backend delta and a precise rollback plan. Only then ask the owner to approve the exact cutover package. Archive/project deletion is separate.

The existing frontend contract suite is useful software evidence but does not prove real PWA original-file access or human acceptance. The Writer fixture is useful component evidence but does not complete the 37-rule clinical acceptance or normal ChatGPT restricted integration.
