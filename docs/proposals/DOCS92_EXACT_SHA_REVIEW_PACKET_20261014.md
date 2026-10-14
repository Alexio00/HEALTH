# HEALTH PR #92 — exact-SHA документационный pre-review и release packet

**14.10.2026. Режим: технический pre-review координатором / НЕ независимая приёмка автором, не owner GO.**
Target: [Draft PR #92](https://github.com/Alexio00/HEALTH/pull/92), branch `docs/current-maintained-guides-20261014` -> `main`.
Freeze BASE `3409791f1ffc5749020e7ff07139b0cec722f6fc`, HEAD **`94f4d61e18e0aecf1ce8d5cdac14ba4b38d90a09`** (после устранения замечания про непринятые Scheduler launchers и уточнения полей REC). При изменении HEAD/BASE **весь review packet stale**.

## Объём и фактически проверенные доказательства

- PR по GitHub readback — **Draft, 7 files**, все исключительно Markdown:
  `README.md`,
  `docs/ARCHITECTURE.md`,
  `docs/BACKUP_AND_RECOVERY.md`,
  `docs/CURRENT_DOCUMENTATION.md`,
  `docs/DATA_MODEL.md`,
  `docs/DOCUMENTATION_AUDIT_RU_20261013.md`,
  `docs/SECURITY.md`.
- Full diff/Filenames сверены через GitHub на этой линии, никакого `scripts/`, `.github/workflows/`, `supabase/`, `frontend/`, `AGENTS.md` изменения нет.
- Приватные **действующие** Project State/Manual прочитаны 14.10.2026. State сообщает: Supabase ACTIVE; Writer ENABLED, accepted exact `main` SHA выше, 270 REC; старый SHEDULLER продолжает backup 03:00 Europe/Moscow; Owner exact-SHA manual tech release установлен, Issue #50 HIGH OPEN. Текущие приватные документы авторитетнее публичных исторических снимков.
- Проверка документации на HEAD до последней узкой поправки: локальные Markdown links всех семи файлов ведут на существующие пути в дереве HEAD, нет буквальных private Google Docs URL / Drive locators / email. HEAD-поправка была в одном `DATA_MODEL.md`, поэтому **необходима финальная повторная автоматическая проверка всех семи файлов на final exact HEAD** до утверждения.
- `HEALTH code validation` GitHub Actions на final HEAD: **SUCCESS**, но это PR-controlled CI, не независимый trust issuer.
- Принятый `main` по повторному readback не изменился на момент проверки; защитный main Ruleset 25010398 ACTIVE. Эти статусы требуют непосредственно pre-merge readback.

## Обнаруженные и исправленные проблемы кандидата

1. Русский `ARCHITECTURE.md` ранее формулировал, что `main` уже имеет trusted Scheduler launchers. Исправлено на: launchers **только Draft / не активированы**. Production backup остаётся в SHEDULLER.
2. `DATA_MODEL.md` укоротил перечень полей `records`; добавлены `type`, `tags`, `source_label`, `source_request_id`, `source_pages`; указано, что новая вакцинационная схема ещё не принята.
3. Возвращены/уточнены security/RLS/default grants/auth и public `health_writer_authorize_v1` exception, backup Source/Writer restart и reproducibility invariants, чтобы перевод не стер действующие ограничения.

## Обязательные проверки независимого аудитора перед GO

| Проверка | Текущий результат | Gate |
|---|---|---|
| Exact BASE/HEAD, seven-path diff | PASS — GitHub metadata | Повторить по HEAD непосредственно перед GO |
| GitHub code validation | PASS на финальном HEAD | Не заменяет независимую приёмку |
| Scope: no executable, SQL, workflow edits | PASS по paths/diff | Подтвердить на финальном SHA |
| Локальные Markdown links, отсутствие private URL/email | PASS до финальной 1-файловой поправки | Повторить на **точном** финальном HEAD |
| Действующий private State/Manual vs public texts | Выполнен архитектурный cross-check | Аудитор независимо сверяет смысл |
| **Нет потери технической семантики из английских оригиналов** | **NOT VERIFIED независимо** | Ключевой документальный risk: compare every removed invariant to Russian replacement/linked authoritative doc |
| Внешние links / страницы документов / команды | **NOT VERIFIED** | Проверить независимым read-only review |
| Actual Supabase permissions / Writer broker / backup runtime | **NOT RUN** (не входят в docs-only PR) | Не объявлять production security PASS |
| Required independently authored verdict / owner GO | **NOT RECEIVED** | Merge NO-GO до отдельных решений |

### Отдельные негативные сценарии для аудитора

- N-01: удалить из мысленного redlined diff границу accepted Writer SHA и проверить, что текст **не** разрешает docs-only merge без reaccept.
- N-02: прочитать сокращённую инструкцию backup как будто HEALTH Scheduler уже работает: должно быть явно ложным, требуется сохранённый private SHEDULLER.
- N-03: прочитать PWA `static` как independent trusted policy: документ обязан упоминать HIGH #50.
- N-04: искать в публичном тексте операционную инструкцию клинического SQL/admin fallback и прямые private document links — не допускается.
- N-05: попытка трактовать старые `PROJECT_STATE/PROJECT_MANUAL` snapshots как актуальные — должна быть отвергнута.
- N-06: сверить каждую заменённую главу `SECURITY`, `ARCHITECTURE`, `BACKUP`, `DATA_MODEL` со старой: сжатие не должно устранять важный технический запрет.

## Предлагаемый release sequence; без автоматического merge

1. Freeze exact candidate SHA, независимый аудит полного diff и документационных инвариантов. Любой fix меняет HEAD и требует нового review.
2. Product Owner даёт **отдельный технический GO**, называя full exact HEAD SHA и scope docs-only; общий ранее выданный GO Writer нельзя переиспользовать.
3. Pre-merge readback: main base, PR head, seven paths/diff, CI/status, Rulesets, unresolved threads; проверить, нет ли параллельного main релиза. **Не** ретаргетить в `pwa` / `writer-code`.
4. Любое изменение `main`, включая этот PR, меняет active Writer code SHA. Поэтому сначала одобренный единый Writer-main reaccept plan: GitHub accepted SHA variable, signed Edge broker policy, SQL runtime code pin и тесты авторизации, при сохранении client trust. Нельзя оставлять активный Writer в случайно остановленном или самопроизвольно разрешённом состоянии.
5. Только после согласованных exact-SHA review/GO — GitHub merge согласно Ruleset; затем postrelease branch SHA/Docs link/readback и **фактическая** проверка Writer authorization fail-closed/restore. Откат — новый reviewed `main` commit с отдельным Writer pin reaccept, **не** force push и не переписывание истории.
6. Документационные дубли PR #33 и #60 не закрывать автоматически. У #33 есть кодовые изменения Source Writer, отсутствующие в #92, требующие самостоятельного scope/release review.

**Verdict координатора:** DOCS-CANDIDATE PREPARED / INDEPENDENT ACCEPTANCE PENDING / MERGE NO-GO. Ни CI, ни данный отчёт не создают полномочий менять принятый `main`. Отсутствие независимого автора-аудитора — сознательно непересекаемая граница.
