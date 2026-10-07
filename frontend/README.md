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


## Table filtering rule

Every table rendered on GitHub Pages must use the shared filterable-table pattern:
- one filter field per column in the table header;
- all filters empty by default, so the full dataset is visible;
- filtering updates immediately while the user types;
- no separate Apply button.

The Records index additionally has global date-from/date-to filters and an exact multi-tag filter. Tags rendered in the Records table are clickable: clicking a tag immediately adds it to the active tag filter and refreshes the table. Active tag filters are removable individually.

Questions in Current State use the same collapsible card pattern as chronic states and open cases.
