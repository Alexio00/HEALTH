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

- Every table shown on GitHub Pages must provide a filter field for every column in the table header.
- Table filters are empty by default and must not hide any rows until the owner enters a filter.
- Filtering is immediate; no separate Apply action is used.
- The Records index additionally provides global date-from/date-to and multi-tag filters.
- Tags in the Records table are interactive filter controls: selecting a tag immediately adds it to the active tag filter.
- Current State questions use the same collapsible-detail reading pattern as chronic states and open cases.
- These are presentation rules only; they must not weaken read-only browser access or embed medical data in the public repository.
