# MVP Plan

## Objective

Build a small vertical slice that proves the new architecture before any full migration.

## Phase 1 — live target bootstrap — PASS

Completed:
- Supabase project connected;
- core schema applied;
- RLS and browser grants hardened;
- secure default privileges activated;
- exactly one allowed Auth reader registered;
- anonymous table access denied;
- authenticated owner SELECT verified;
- authenticated INSERT/UPDATE/DELETE denied;
- technical tables hidden from browser roles;
- read-only PWA deployed through GitHub Pages;
- owner verified successful browser authentication.

## Phase 2 — representative migration subset — PASS

Completed:
- dependency-safe representative subset imported from the canonical Drive-native HealthDB;
- ordinary records, source links, laboratory data, a complete Case chain and current-state entities covered;
- deterministic random standalone records included;
- existing record IDs preserved;
- exact source-derived laboratory literals preserved;
- source and target compared;
- import finalized only after validation PASS.

Detailed medical identifiers remain private.

## Phase 3 — source copy — PASS

Completed:
- required representative Source material copied;
- provider-neutral logical source metadata and physical PRIMARY/BACKUP locations created;
- target size/checksum verified;
- provenance links preserved.

## Phase 4 — read-only PWA — PASS

Completed:
- Current State;
- Closed Cases;
- Records index;
- Case chronology;
- REC body;
- direct authenticated Source opening;
- sorting/filtering/navigation;
- owner visual verification;
- installable static PWA;
- first-party frontend JavaScript boundary with no runtime third-party JS CDN.

## Phase 5 — backup / restore — PASS

Completed:
- independent database backup;
- independent Sources backup;
- checksums/manifests;
- backup readback;
- isolated MVP restore test;
- scheduler bootstrap;
- sequential daily backup pipeline;
- enabled schedules.

Post-MVP hardening also preserves the live Supabase migration history in future database backups.

## Phase 6 — operational acceptance — PASS

MVP operational acceptance is complete.

## Pre-full-migration hardening

The project now has:
- canonical timestamped `supabase/migrations/`;
- exact security/Auth invariant scripts;
- a private-package full-migration runner with seal/verify/stage/compare/guarded commit;
- explicit old-HealthDB freeze semantics;
- Auth recovery documentation;
- hardened scheduler tooling.

Remaining owner gates are recorded in `docs/PROJECT_STATE.md`.

Full migration begins only after explicit owner approval after the final pre-migration audit.
