# Frontend

The frontend is a static, read-only PWA deployed through GitHub Pages.

## Navigation

- **Состояние** — current state with questions, chronic states, open cases, medications, monitoring and future plan.
- **Закрытые случаи** — collapsible closed-case register with opening/closing REC links and the imported case chain.
- **Записи** — table index with REC, date, tags, type, confidence, summary and case links.
- **Карточка случая** — chronology of OPEN / CONTINUES / CLOSES relations.
- **REC** — full record text, related cases and Sources.
- **Source** — provider-neutral metadata and owner-only Google Drive locator.

The UI deliberately mirrors the useful reading patterns of the legacy HealthDB files while reading live structured data from Supabase.

## Security boundary

- Browser access is SELECT-only.
- Anonymous users cannot read medical tables.
- Medical data is never embedded into the public repository or static Pages assets.
- Google Drive object IDs are returned only after authenticated database access.


## Table sorting and filtering

All data tables use sortable column headers. Click a header to toggle ascending/descending order; there is no separate row of per-column text filters.

Compact filter bars appear only when they add value:
- date ranges where relevant;
- repeated categorical values as live select controls;
- Records: date range, Tag, Record Type and Confirmation when available;
- Future Plan: repeated Kind and Status values;
- Closed Cases: closing date and Category when multiple categories are present.

Record tags are clickable. A tag click immediately opens the Records index with that tag active. Filters default to All/empty, so no rows are hidden by default.

REC presentation is owner-facing rather than migration-facing: legacy YAML/frontmatter is hidden, technical source roles/hashes are not shown, Sources open the primary Google Drive original directly, and source page numbers remain visible because they locate the evidence inside multi-page originals.
