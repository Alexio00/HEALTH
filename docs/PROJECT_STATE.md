# Project State

Status: Representative MVP import PASS; visual data check and backup/restore pending

## Confirmed

- Public repository `Alexio00/HEALTH` is intentionally safe for public inspection.
- Private scheduler repository `Alexio000/SHEDULLER` is connected with administrative/write access.
- Primary target Sources storage exists on the private owner Drive.
- Independent backup Drive folders exist.
- Existing Drive-native HealthDB remains the canonical source of truth until explicit cutover.
- Supabase project `HEALTH` is connected and healthy.
- Core schema, RLS, secure browser grants and secure default privileges are active.
- Exactly one approved Auth reader is configured.
- Auth and database security invariants PASS.
- Read-only PWA is deployed through GitHub Pages and owner authentication is confirmed.
- PWA navigation now mirrors the useful reading structure of the legacy HealthDB: Current State, Closed Cases, Records Index, Case card, REC and Source.
- Current State uses collapsible case blocks; Closed Cases has a separate collapsible register; Records is a linked table index.
- All PWA tables use per-column header filters with empty defaults and immediate filtering.
- Records also has global date and multi-tag filters; table tags are clickable filter controls.
- Current State questions use the same collapsible-detail pattern as chronic states and open cases.
- A small representative medical subset has been copied from the canonical Drive-native HealthDB into the new database.
- The representative subset includes record text, source linkage, laboratory rows, a complete Case relation chain and current-state entities.
- Required source material for the subset has been copied into the new private `HEALTH/Sources` storage.
- Source copy verification included an independent SHA-256 recomputation.
- Source-to-target fidelity checks PASS.
- The representative import operation reached FINALIZED only after all active checks PASS.
- Detailed migrated medical identifiers and acceptance evidence are stored only in the private target database, not in this public repository.
- No source-system data was deleted or moved.
- No cutover has occurred.
- Full migration has not begun.

## Remaining MVP work

- Owner visual check of imported data in the live PWA.
- Portable database backup.
- Independent Sources backup to the second Drive account.
- Backup manifest/count/checksum verification.
- Restore test.
- Final MVP acceptance decision.

## Known non-blocking infrastructure findings

- Supabase Security Advisor reports leaked-password protection disabled; this is an Auth hardening item, not a data-fidelity failure.
- Performance Advisor reports several unindexed foreign keys; acceptable for the tiny MVP but should be addressed before full migration.

## Next gate

Verify the imported subset in the live PWA, then complete backup/restore. Full migration remains blocked until explicit owner approval after final MVP review.
