# Health API

## Purpose

AI clients operate through domain-level server functions. They must not receive unrestricted SQL or database-admin credentials.

## Read operations

- `activate`
- `search_records`
- `get_record`
- `get_current_state`
- `get_case`
- `get_labs`
- `get_source`

## Mutating operations

- `begin_operation`
- `create_record`
- `update_record`
- `import_labs`
- `attach_source`
- `add_question`
- `update_plan`
- `validate_operation`
- `finalize_operation`

## Rules

- Every mutation requires an operation ID.
- The server enforces the single-writer invariant.
- Low-level multi-table writes stay server-side.
- Validation failures prevent finalization.
- Source metadata and physical source upload are separate operations internally.
- API errors are explicit and fail closed; no partial success is silently treated as complete.

## Authentication

PWA users and AI writers are separate trust classes.

The browser is read-only. AI-write credentials are server-side only.
