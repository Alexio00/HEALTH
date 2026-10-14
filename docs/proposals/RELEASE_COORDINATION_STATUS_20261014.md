# HEALTH — ближайший план технической координации и выпуска

**Рабочий снимок 14.10.2026. Статус: DRAFT / coordination-only / не управляющий документ.**
Авторитет: действующие приватные `HealthDB — Project State` и `Project Manual` плюс фактический принятый GitHub/Supabase runtime. Исторические GitHub-документы не заменяют их. Перед выпуском повторить live readback.

## Проверенные исходные границы

| Контур | Точный SHA на дату сверки | Статус |
| --- | --- | --- |
| `main` (accepted Writer runtime/code pin) | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | Production принят ранее, **не менять** в этой задаче |
| `writer-code` | `7d67ae96b8f8e344321a4df87e467fff71a20652` | PR #91 MERGED; Browser Consent — только неавторизующая policy |
| `pwa` | `c97bb4fc3d9bdf4321a360c437a1460a9b06e1bc` | PR #80/#85 MERGED; GitHub Pages release workflow #38615109542 SUCCESS, HTTP/MIME/SHA/full-byte postcheck SUCCESS; **authorized-session UI smoke NOT RUN** |
| `scheduler-code` | `41f83d9aed64171bb08b3ce353ad6392179b8467` | PR #95 MERGED/R6-B PASS по переданному независимому протоколу; **новый Draft #96 OPEN** |
| `scheduler` | сверять live отдельно | Только heartbeat, не production backup engine |

Production backup и keepalive ещё остаются в приватном SHEDULLER. Принятый Writer зависит от точного `main` SHA, подписанного broker policy и runtime pin. Любой docs-only merge в `main` изменяет SHA и поэтому не является свободным выпуском. PWA release из `pwa` не переиздаёт медицинскую авторизацию.

## PWA #80/#85 — independently checked release checkpoint (14.10.2026)

- [PR #80](https://github.com/Alexio00/HEALTH/pull/80) MERGED first into `pwa`, merge SHA `d42b53d9650aa1cdfa48f84ba83d58d9cbd6d23d`. [PR #85](https://github.com/Alexio00/HEALTH/pull/85) MERGED after independent acceptance of HEAD `accb4e50db1bd4269ee10f606e6143c86d903c3d` over BASE `d42b53d9650aa1cdfa48f84ba83d58d9cbd6d23d`.
- Final `pwa` release/merge SHA **`c97bb4fc3d9bdf4321a360c437a1460a9b06e1bc`**; #85 merge changed **only** `frontend/README.md`, `frontend/app.js`, `frontend/styles.css`, `frontend/tests/contract.mjs`; `frontend/vaccination.mjs` from accepted #80 is unchanged.
- [Deploy HEALTH PWA run #38615109542](https://github.com/Alexio00/HEALTH/actions/runs/38615109542), event `push`, exact final release SHA: **completed/success**. Three independent jobs successfully ended: `Verify PWA before release`, `Publish verified PWA`, `Verify published release bytes` (HTTP/MIME/SHA/full-byte gate). Separate postmerge `HEALTH code validation` run **#38615109608** completed/success. Published URL: https://alexio00.github.io/HEALTH/.
- User-provided release executor reported 15 files and `root: PASS`; coordinator independently re-read run/job conclusions but **did not independently rerun file-byte check or an authorized browser login**. **Authenticated production UI smoke = NOT RUN**, recorded as a narrow optional follow-up; neither a retroactive PR #85 FAIL nor a new authorization for clinical data processing. Existing HIGH #50 stays OPEN.
- Current `main` accepted Writer code SHA **unchanged** (`3409791f1ffc5749020e7ff07139b0cec722f6fc`); no Supabase/Writer/clinical schema changes. UI-specific development for #80/#85 is complete. Further vaccination canonical reader work depends separately on Issue #62.

## Непосредственная очередь задач без параллельного дублирования

| Приоритет | Трек / ответственное направление | Уже готово | Что реально остаётся / блокер | Следующий проверяемый результат |
| --- | --- | --- | --- | --- |
| P0 — сохранять работу | Production / Owner + Ops | ACTIVE backend и прежний Scheduler | Не трогать production pin, Source/backup, single Writer; мониторить принятый live контур | Безопасная непрерывность, старый SHEDULLER не отключать |
| P1 | **Scheduler Operations**, [#65](https://github.com/Alexio00/HEALTH/issues/65), [#87](https://github.com/Alexio00/HEALTH/issues/87) | PR #95 в `scheduler-code` | Draft #96, final exact pinned launchers в `main`, zero-in-flight, legacy-pause, реальный восстановимый complete archive, полный restore, rollback; техдолг R5B-M01 | Отдельный **OPERATIONS ACCEPTANCE** пакет и явное OWNER_GO перед cutover |
| P1 | **Writer Development**, [#34](https://github.com/Alexio00/HEALTH/issues/34) | PR #91 слит в `writer-code` | Private preapproval-preview, trusted `review_sha`, Auth/session/CSRF, одноразовый CAS, независимый signed issuer и E2E. `POLICY_MATCH_ONLY` — не consent. | Изолированный проверяемый кандидат preview, затем независимая проверка |
| P1 | **Schema/Writer/Vaccination v2**, [#62](https://github.com/Alexio00/HEALTH/issues/62) | Draft [#83](https://github.com/Alexio00/HEALTH/pull/83), исправления A62-C1; приватный locator удалён из текущего HEAD [#45](https://github.com/Alexio00/HEALTH/pull/45) | Independent `ARCHITECTURE_CONTRACT_FAIL` 2 BLOCKER/5 HIGH/2 MEDIUM; one transactional six-table DDL, `42704` fix, deterministic key strategy, dependency/current-proof, Verifier/Validation and PG17 E2E **NOT RUN**; historical privacy exposure needs owner disposition | Один bounded SQL/contract corrective package + **адресный** A62-01…09 audit; Issue #62 не закрывать |
| P2 | **PWA Development** | PR #80/#85 merged, verified GitHub Pages release + postmerge `static` on exact `pwa` SHA | Только **ручной authorized-session smoke NOT RUN**; старый #59 — legacy REC/plan projection, не canonical vaccination graph | При необходимости один ограниченный браузерный smoke, без повторного аудита #85; Reader V2 только **после** принятия backend contract |
| P2 | **Documentation**, [#61](https://github.com/Alexio00/HEALTH/issues/61) | Документы `main` в [#92](https://github.com/Alexio00/HEALTH/pull/92) получили независимый `DOCS_ACCEPTANCE_PASS` на `cfd213fb992d61a1520e7426ce8797c81e2107ab` | #92 freeze / не редактировать; выпустить в согласованном `main` окне. Англоязычные `frontend/README.md` и `docs/PWA_RELEASE.md` в `pwa` требуют русского пользовательского/эксплуатационного текста в **отдельной pwa-docs ветке** | Узкий перевод только действующих руководств, diff/links/privacy/static review; historical audits без перевода |
| P3 | Documentation/backlog hygiene | Текущая release-train inventory #83 | Дубли #33/#60, устаревшие #76/#69, draft ветки и private locator history **не удалять без отдельного решения** | Список owner решений; после принятия main — проверка supersession и адресное закрытие старых PR |

## Разделение полномочий

- **Архитектурный чат:** current technical status, таблица зависимостей, точные SHA, проверка соответствия A62-01…09, архитектура release gate, анализ дубликатов, документация без production воздействий.
- **Writer:** код Writer/preapproval-preview и schema/delta/Verifier/Validation; без автономной публикации медицинских данных.
- **PWA:** UI и его документация строго в `pwa`; не превращать REC heuristics в верифицированные vaccination events.
- **Scheduler Code:** исправление отдельного Draft #96, регрессионные/fault тесты; не трогать старый production.
- **Scheduler Operations:** independently verified external/legacy continuity, launcher pins, zero-in-flight, complete restore and safe cutover.
- **Independent auditors:** exact immutable SHA и scope-specific negative tests. **Product Owner:** решение о выпуске и варианте обработки исторического private URL; никакого автоматического GO.

## Общий выпуск `main`: обязательные входные условия

1. Для каждого кандидата отдельный `BASE_SHA`/`HEAD_SHA`, target, file/diff/CI/Rulesets/threads и verdict. Не переносить PASS со старого SHA и не считать зеленый PR CI самостоятельным независимым аудитом.
2. Составить один явный release manifest: какие принятые, не конфликтующие изменения Writer/launcher/docs действительно входят в `main`; schema v2 и Scheduler cutover — **не** автоматически включённые элементы.
3. Подтвердить возможность безопасно приостановить и вновь включить bounded Writer, текущие операции и источник подписанной авторизации, а также обновить `main` accepted code SHA, broker и runtime pin **без рассинхронизации**; проверить необходимые защищённые workflow и реальный rollback.
4. **Отдельный Owner GO** на точный executable/documentation release и postmerge SHA. Без GO: NO MERGE; никаких автоматических проверок, которые способны заменить владельца.
5. Только после контролируемого выпуска — readback точного `main` SHA, CI, Writer fail-closed/authorized test без клинических данных, соответствие broker pin и наблюдаемая доступность. Любое изменение main invalidates старую SHA-приёмку.
6. **Scheduler production cutover — отдельный gate и отдельный GO**, даже если его код и launchers когда-либо попали в `main`. Не выключать SHEDULLER до фактического backup/restore доказательства и zero-in-flight.

## Документация: конкретный оставшийся долг

- **Не возвращаться к аудитам #92:** этот SHA уже независимо принят. После согласованного release window можно проверить, что действующая навигация ссылается на актуальные документы, и закрыть дубли только после owner-approved diff-based решения.
- **PWA-документация ещё на английском**: `frontend/README.md`, `docs/PWA_RELEASE.md` — техдокументы действующего интерфейса и его release. Переводить смысл без изменения команд, SHA, route имен, требований `static` и уязвимых мест Pages. `README` в `main` из #92 не заменяет этот фронтенд-трек.
- **Риски/долги, не переписывать молча:** privacy locator был убран из current #45 HEAD, **но не** из истории; guard пропускает `.md` и email; Manual имеет историческую нумерационную несогласованность. Управляющий Manual меняется только по отдельному owner decision. Инцидентный private locator не воспроизводить в публичных комментариях.
- **Исторические audit/evidence файлы на английском не переводить**, не удалять. Старые Draft PR и branches не чистить автоматически.

## Статус

Этот документ — **план координации на дату сверки, не релизный манифест**, не proof прохождения клинических/операционных тестов, не production runtime readback. Изменён только Draft #83; сохраняются все границы `main`, `writer-code`, `pwa`, `scheduler-code`, `scheduler`, приватного SHEDULLER и реальных медицинских данных.
