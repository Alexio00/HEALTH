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
- selected a small dependency-safe subset from the canonical Drive-native HealthDB;
- included ordinary records, source-linked records, laboratory data, a complete Case relation chain and current-state entities;
- added deterministic random standalone records to reduce cherry-picking bias;
- preserved existing record IDs;
- preserved exact source-derived laboratory literals;
- compared source and target exactly;
- finalized the import only after validation PASS.

Detailed medical identifiers are retained privately in the target database and are intentionally not committed to this public repository.

## Phase 3 — source copy — PASS

Completed:
- copied only source material required by the representative subset;
- created provider-neutral source metadata and a physical primary location;
- verified target file size;
- independently recomputed SHA-256 and matched the canonical source;
- preserved provenance links.

## Phase 4 — read-only PWA with real MVP data — IN PROGRESS

Implemented:
- Current State;
- Index;
- Record;
- Source opening.

Pending:
- owner visual verification of imported content and source navigation on the live site;
- mobile/installability check.

## Phase 5 — backup / restore — NEXT

- create a portable MVP database dump;
- copy MVP source files to independent backup storage;
- create manifest with counts/checksums;
- verify the backup;
- restore the dump into an empty PostgreSQL target;
- verify restored IDs and relations.

## Phase 6 — acceptance report

The public repository contains only a non-sensitive template.
The populated acceptance evidence belongs in the private target database.

Full migration begins only after explicit owner approval.
