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

- Every table shown on GitHub Pages must support sorting by clicking its column headers.
- Column headers show a neutral sort indicator and then the active ascending/descending direction.
- Do not add a separate text-filter row under table headers by default.
- Add a compact filter bar above a table or card collection when the underlying data has meaningful repeated structured values such as tags, record types, evidence/confidence categories, case categories, statuses or other stable enumerations.
- Omit categorical controls when the current view contains only one possible value.
- Filter controls are empty by default, show all data and apply immediately without a separate Apply action.
- The Records index provides date-from/date-to, tag, record-type and confirmation filters. Tags in the table and on a REC page are interactive and immediately open/apply the corresponding Records tag filter.
- Current State questions use the same collapsible-detail reading pattern as chronic states and open cases.
- User-facing REC pages prefer human-readable Russian labels and content. Technical storage/provenance fields remain in the database but are hidden when they do not help the owner read the medical card.
- Source links from a REC open the original private source directly. Technical relationship roles and file-integrity hashes remain internal.
- Exact source-page locators remain visible because they help the owner find supporting material in the original source.
- These are presentation rules only; they must not weaken read-only browser access or embed medical data in the public repository.
