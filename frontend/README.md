# Frontend

The frontend is a static, read-only PWA deployed through GitHub Pages.

## Navigation

The mobile menu is collapsed by default (hamburger button); the desktop header
keeps a wrapping horizontal navigation. Routing opens the requested page,
not a menu. Current State is a composite view; other pages reuse the same live
rows without copying or synchronizing duplicate medical entities.

1. Текущее состояние — questions about chart conflicts or chart actions, chronic conditions,
   open episodes, medications, monitoring, visit preparation, future plan.
2. Хронические состояния
3. Открытые случаи
4. Принимаемые препараты
5. Мониторинг
6. Подготовка к визиту
7. Будущий план
8. Закрытые случаи
9. Записи
10. Вакцинация — deliberately empty until the owner provides content.

Visit preparation groups plan items explicitly marked as visits/consultations and
open specialist questions. Specialties are determined only by explicit source
wording (normally the prefix before the colon); questions may be shown for
multiple explicitly named specialists. No matching planned appointment is
invented when a question has no corresponding plan item. Data lives in the
existing plan_items/questions tables, not copied UI state.

Questions marked metadata.category=medical_card (or
metadata.purpose=medical_card) remain in Questions on Current State.
The pre-existing MVP specialist questions are displayed only under Visit
Preparation by default.

The UI deliberately mirrors the useful reading patterns of the legacy HealthDB files while reading live structured data from Supabase.

## Security boundary

- Browser access is SELECT-only.
- Anonymous users cannot read medical tables.
- Medical data is never embedded into the public repository or static Pages assets.
- Google Drive object IDs are returned only after authenticated database access.


## Table sorting and filtering

All data tables use sortable column headers. Click a header to toggle ascending/descending order; there is no separate row of per-column text filters.

Table header display contract (REC markdown tables and top-level pages alike):
- Center header text horizontally and vertically.
- Word wrapping is allowed only between complete words; never split single
  words letter-by-letter just to fit the viewport. A horizontally scrollable
  table is preferred over breaking "Результат", "Референс" or "Параметр".
- Vertical padding above and below is half of one line height each, and
  remains unchanged when a header wraps to additional lines.
- The visible word "Количество" (standalone or in a multiword header) is
  abbreviated as `К-во`; source text and the accessible sorting label remain
  unchanged.


Compact filter bars appear only when they add value:
- date ranges where relevant;
- repeated categorical values as live select controls;
- Records: date range, Tag, Record Type and Confirmation when available;
- Future Plan: repeated Kind and Status values;
- Closed Cases: no filters (the list is read directly).

Record tags are clickable. A tag click immediately opens the Records index with that tag active. Filters default to All/empty, so no rows are hidden by default.

## Scrolling / sticky chrome

All page titles are sticky directly beneath the site header. The title's
initial top margin is reduced to give more reading space. No page-introduction
paragraphs or duplicated standalone section titles appear; Current State
retains its multiple named sections.

On single-table pages (Records and Future Plan), the existing filter bar
remains pinned between the page title and the table header. The Closed Cases
list no longer has date/category filters.

Table headings remain visible during vertical scrolling. Native CSS sticky
headings cannot stick to the viewport inside the horizontally scrollable
table wrapper, so a position-fixed, width-aligned header mirror is used while
the real table header has scrolled off. Horizontal table scroll positions and
sorting buttons are synchronized to the original table; the mirror is hidden
outside its owning table. Global header height and sticky title height are
measured dynamically to accommodate desktop wrapping and the mobile menu.
This is presentation-only and does not change row contents or filtering.


REC presentation is owner-facing rather than migration-facing: legacy YAML/frontmatter is hidden, technical source roles/hashes are not shown, Sources open the primary Google Drive original directly, and source page numbers remain visible because they locate the evidence inside multi-page originals.


## REC body cleanup

REC pages show owner-facing medical content, not migration wrappers:
- legacy BEGIN/END FILE and REC wrapper lines are hidden;
- duplicated legacy metadata/frontmatter is hidden when the same values are already shown in the REC header;
- the first H1 is used to derive the page title and is not repeated inside the Text Record section;
- internal record headings have spacing before the heading and no extra spacing after it;
- raw medical body_text remains unchanged in the database.
