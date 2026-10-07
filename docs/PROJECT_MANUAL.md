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
