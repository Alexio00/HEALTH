# Project Manual

## Modes

- **read-only** — inspect, search, compare, validate.
- **maintenance** — change code, schema, automation, metadata, validation or technical state.
- **import** — copy or modify real medical data only under explicit owner authorization.

## Public-repository rule

Real medical data, source files, private filenames, provider file IDs/URLs, account identifiers, passwords, tokens, private keys and production `.env` values are forbidden.

Use synthetic fixtures for tests.

## Write model

Medical writes must use one logical operation:

`PREPARED -> COMMITTED_REGISTRY -> VALIDATED -> FINALIZED`

Interrupted work becomes `FAILED`.

The database must enforce a single unfinished mutating operation.

## Provenance

Do not invent missing data. Empty, absent and explicitly negative values are different states.

For laboratory observations, preserve literal source value, precision, units, reference range and source flag.

## Source abstraction

Canonical source identity consists of `source_id` plus `logical_path`. Physical storage belongs in source-location rows.

## MVP gate

Full migration is forbidden before owner approval of a working vertical slice with:
- representative records
- source opening
- laboratory data
- case links
- authentication/RLS
- backup/restore test
- old-to-new comparison
- latency and validation report

## Cutover

The legacy/current health database stays authoritative until the owner explicitly approves cutover.


## PWA table and navigation conventions

- Every table shown on GitHub Pages must support sorting by clicking the column title.
- Column headers use a neutral bidirectional sort marker by default and show ascending/descending direction when active.
- Do not render a separate text-filter row under table headers.
- Add a compact filter block before a table or card collection when the dataset has useful categorical/repeating values or a meaningful date range.
- Repeating categorical values should use select controls populated from the live dataset; filters are empty/All by default.
- The Records index always provides date-from/date-to and tag filters, and additionally exposes repeated Record Type / Confirmation values when more than one value exists.
- Tags in the Records table and REC page are interactive filter controls; selecting a tag immediately opens/updates the Records index with that tag active.
- Current State questions use the same collapsible-detail reading pattern as chronic states and open cases.
- Sources linked from a REC should open the original primary Google Drive object directly when a primary locator exists.
- Technical provenance fields such as link role and source hashes stay in the database/validation layer unless the owner explicitly asks to inspect them.
- These are presentation rules only; they must not weaken read-only browser access or embed medical data in the public repository.
