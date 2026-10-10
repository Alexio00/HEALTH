# Health API (deferred design candidate)

**Status: FUTURE OPTION / NOT IN DEVELOPMENT.** No deployed Health API or PostgreSQL RPC writer is implied by this document. The accepted MVP is read-only. See [Write-path decision](WRITE_PATH_DECISION.md).

## Current operational decision

Until owner-authorized cutover, the active Drive-native HealthDB remains canonical, including **ordinary owner-authorized medical changes performed by ChatGPT or another AI through the currently connected Google Drive workflow** under its active Project Manual/State. The new HEALTH platform is a separately validated read-only MVP plus an independently authorized *one-time migration* channel. Do not interpret the existing privileged migration SQL or a generic Supabase connector as an approved day-to-day writer.

The owner wishes to retain a conversational AI + connector workflow after cutover; its safe SQL/Sources implementation and actual connector support remain to be designed, verified and separately accepted. There is **no current development mandate** for either design candidate below.

## Candidate 1 — dedicated Health API (future)

AI clients would call narrowly scoped domain-level server functions, never unrestricted SQL or database-admin credentials.

Potential read operations: `activate`, `search_records`, `get_record`, `get_current_state`, `get_case`, `get_labs`, `get_source`.

Potential write operations: `begin_operation`, `create_record`, `update_record`, `import_labs`, `attach_source`, `add_question`, `update_plan`, `validate_operation`, `finalize_operation`.

The trusted server enforces writer authorization, single-writer semantics, transaction boundaries, NNN ownership, validation freshness, original-source verification and recovery. This design is **deferred**, not scheduled.

## Candidate 2 — restricted PostgreSQL RPC/stored procedures (future alternative)

AI connector could invoke a minimal private-schema RPC surface, e.g. `health_begin_operation`, `health_create_record`, `health_import_labs`, `health_validate_operation`, `health_finalize_operation`, instead of a separate Health API server.

Potential advantages: smaller application layer and atomic PostgreSQL writes. Trade-offs: least-privilege caller credentials and `EXECUTE` grants, function security, provider-specific source upload/verification outside SQL, retries and compensation on cross-provider partial failure. PostgreSQL `SECURITY DEFINER` must never be used as an unreviewed bypass of RLS/authorization. Confirm the selected AI connector actually supports such narrowly scoped calls.

This is **only an architectural idea**, not an implemented, tested or authorized mechanism.

## Common non-negotiable requirements

Whichever implementation is eventually chosen, it must enforce:

- Explicit owner authorization for every real medical mutation; no automatic import of attachments.
- `public.operations` single-writer lock, `PREPARED -> COMMITTED_REGISTRY -> VALIDATED -> FINALIZED` or auditable `FAILED`; no privileged DML bypass.
- Atomic NNN reservation/ownership and no reuse of used/retired IDs; idempotent retries.
- Literal lab/provenance fidelity; physician/clinical decisions and OPEN/CLOSES owner gates.
- Dependable Google Drive Sources materialization, SHA-256 readback, locator updates and crash recovery.
- Operation-bound mechanical and semantic Validation, including new active-medication interaction-check question (not fabricated for historical migration).
- Properly restricted writer identity; browser remains read-only.
- End-to-end tests on synthetic data and a separate owner acceptance for the actual post-cutover writer.

**Decision:** do not build Health API or RPC now. The full-migration project does not silently authorize either or imply that production writing after cutover is ready.
