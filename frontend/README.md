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
