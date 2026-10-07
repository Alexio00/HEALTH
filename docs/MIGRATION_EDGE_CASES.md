# Migration Edge-Case Rules

These rules supplement the main migration field map. They contain no medical data, filenames, private Drive identifiers or credentials.

## Source checksums

- Compute SHA-256 independently from the bytes of every migrated source file.
- Treat any checksum text stored in the old Registry as a cross-check/provenance value, not as the authority for the copied object.
- If a record contains multiple source URLs and the old checksum field has a different number of values, never pair URLs and checksums by position.
- Preserve the raw old checksum field in private provenance and use the independently recomputed per-file checksum for the HEALTH source row.
- A missing old checksum is not reconstructed from another source; it is recomputed from that file's bytes.

## Multi-record relationships

For Medications, Plan, Questions and future Monitoring rows:

- preserve the complete old `record_ids` list in metadata;
- if exactly one valid REC is listed, it may populate `basis_record_id`;
- if no REC is listed, leave `basis_record_id` null;
- if multiple REC are listed, leave `basis_record_id` null unless another authoritative source field explicitly identifies one basis REC;
- never choose the first/last REC merely by list position.

For Questions, populate `resolved_by_record_id` only when the source explicitly identifies the resolving REC.

## Retired IDs

- HEALTH retired ledger rows keep `record_id = null`.
- Preserve the old retired record identifier, old text operation reference and old note in `id_reservations.metadata`.
- Never recreate a retired identifier as a fake active REC.

## Date coercion

- Parse an exact, unambiguous date when the source supplies one.
- Accept one- or two-digit day/month D.M.YYYY forms for laboratory dates.
- Preserve every raw source date/due string in metadata where required.
- Free-text scheduling expressions never populate a typed date column.
