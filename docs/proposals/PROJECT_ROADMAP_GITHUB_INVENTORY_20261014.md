# HEALTH — полный инвентарь GitHub и roadmap технического проекта

**Рабочая ревизия:** 14.10.2026; **DRAFT / snapshot only**. Этот файл находится в открытом документационном PR #83, **не** является действующим Project State/Manual, разрешением на merge, релиз, медицинскую запись или удаление. Прежде чем действовать, перечитать живые приватные [Project State/Manual] в разрешённом контуре и live API. Не публиковать содержимое приватных документов и IDs/названия Sources.

## 0. Покрытие и количественные итоги

- Публичный `Alexio00/HEALTH`: **20 open Issues**, **24 open PR**, **51 existing branches**, из которых **5 фиксированных контуров**. 24 PR могут делить одну feature-ветку (#64/#71). Ветки без открытого PR **не** означают, что код утрачен или безопасен к удалению.
- Приватный `Alexio000/SHEDULLER`: **5 open Issues**, **13 open PR**, **15 branches** (private GitHub readback). Подробные приватные branch/PR identifiers **не** переносить в публичный документ. Классификация приватных кандидатов — отдельный приватный handoff. Сейчас SHEDULLER — production backup authority.
- Все таблицы ниже — point-in-time GitHub registry; отдельные PR Head SHA могут измениться сразу после фиксации этого документа.
- Контрольные ветки: `main=3409791f1ffc5749020e7ff07139b0cec722f6fc`, `writer-code=7d67ae96b8f8e344321a4df87e467fff71a20652`, `pwa=c97bb4fc3d9bdf4321a360c437a1460a9b06e1bc`, `scheduler-code=0f071b3061d7c3f53b9e637a071b3a2af95d761f`, `scheduler=98f9c41ff9b1496dfc40d0da960971ae7bf58a42`. Main acceptance and live runtime must not be inferred solely from Git branch.

## 1. Delivery roadmap — milestones and gates, no invented deadlines

| Phase | Deliverables / canonical tickets | Accountable team | Required closure evidence | Release gate |
| --- | --- | --- | --- | --- |
| **P0 continuity now** | Keep accepted Writer signed SHA, PWA release, existing SHEDULLER complete daily backup + restore safe; #50 HIGH risk documented/manual scope review | Owner + Operations / Architecture | No alternate Writer, no simultaneous backup rotation; accepted code/backup readback | No production change |
| **P1-A Scheduler Operations** | #65, #87, #82; accepted dev PR #95/#96; compare #72/#89; runbook #86; legacy zero-in-flight, immutable launcher+executor pins | Existing Scheduler Operations chat + independent Ops auditor | Real privately witnessed complete archive, full DB/Auth/roles/Sources restore, zero in flight, two-sided exclusions, scheduled follow-up, rollback; exact SHA evidence | **Separate production cutover OWNER_GO**; no stop/delete SHEDULLER before |
| **P1-B Writer Gateway** | #34; isolated accepted policy PR #91; existing Writer team #84/#35 and preapproval-preview/CAS/broker semantics | **Existing Writer team only** | Synthetic negative E2E, trusted Auth/session/owner evidence, one-time consent, independent verifier, accepted Writer/broker main SHA | Dev branch acceptance != signed clinical authorization |
| **P1-C Vaccination v2** | #41/#62, #45/#83 A62-C1; one transactional six-table SQL, typed plan obligations, correction invalidation, Verifier/Validation, versioned canonical Reader | Existing Writer schema team + Architect + PWA reader after contract | Address A62-01…09, fix SQL 42704, disposable PG17 positive/negative, privacy history owner decision, independent targeted review | No migration/import; Issue #42 remains private separate clinical authorization |
| **P1-D Docs** | #61, independently accepted docs #92 held Draft; separate PWA docs `frontend/README.md` and `docs/PWA_RELEASE.md`, current #83 coordination | Dedicated Docs team | Current Russian operational docs, links/ACL/privacy review, current PWA doc `static`, independent exact-SHA review | Docs merge to main still reaccepts Writer SHA |
| **P2 controlled main release** | Single explicit scope/release manifest for chosen #39/#72/#89/#76/#92 and approved Writer changes; #50 risk/alternative addressed or explicitly accepted under controlling Manual | Architect + release coordinator + Owner + independent reviewer | Freeze exact base/head/diff, code/issuer impact, accepted SHA, signed broker/runtime pin, rollback & postchecks | **Separate technical owner GO; no blanket auto-merge** |
| **P2 Scheduler cutover** | Exactly once switch authority from legacy SHEDULLER, prove new backup and restoration before decommission | Scheduler Operations | Real full archive, future scheduled jobs, skip/missing-run handling and restoration | Separate owner GO; later decommission permission |
| **P3 user features and setup** | #40 scheduling questions; #58 security/MFA design; #74 next Writer error contract; #53 manual/AI single-patient deployment runbook; #55 portability study | Future teams, sequential where shared Writer | Read-only design before schema, minimal architecture, independent test/owner acceptance | No paid services or clinical access without approval |
| **P4 longer horizon** | #54 automation only after #53 approved manual runbook; #75 independent PHR/vNext research; #57 branch/PR/archive hygiene; #19 historical count clarification; private medical #42/#52 | Research/hygiene, private clinical team only if authorized | Evidence-led, maintain original history, no secret/Source exposure, explicit owner decisions | No production/medical action inferred from backlog |

## 2. Dependencies and collisions

1. **NEVER touch accepted production `main` piecemeal.** A docs-only merge changes Writer's accepted code SHA; protected manual exact-SHA review, Product Owner GO, signed authorization broker/runtime pin & rollback all apply.
2. #62 is the exclusive cross-team schema contract. Writer C1 is already in active development. PWA #59 remains legacy REC/plan text projection, **not** migration nor verified canonical vaccination Reader. Existing PWA #80/#85 merged and Pages verified; a live authorized-session smoke is still NOT RUN.
3. Code Scheduler #95/#96 is accepted **in `scheduler-code`**, not deployed. Ops #87 launcher main SHA, old backup exclusion, complete restore and verification are independent gates.
4. #50 mandatory trusted PWA scope issuer is an **OPEN HIGH**; R3 PR #78 **paused/no-go by owner decision**. Do not restart unauthorised automation or treat CI `static` as independent issuer; continue manual exact-SHA reviews required by live Manual.
5. PR families needing diff-based deduplication: `#84/#35` Writer; `#51/#59` vs accepted PWA #80/#85; `#94/#88/#81` vs accepted Scheduler #95/#96; `#72/#89` launcher alternatives; `#64/#67/#71` vs current Scheduler topology; `#33/#60/#92` docs; `#39/#76/#69` branch/governance; historical `#27/#22/#36`. **Never merge or close on title similarity alone.**
6. Feature branch existing after merge = **candidate for careful cleanup**, not deletion authorisation; respect protected refs, historical evidence, PR diff pointers, and Source/privacy retention.

## 3. Open HEALTH Issues — all 20

| Issue | Title | Proposed work queue (NOT GitHub label) |
| --- | --- | --- |
| [#87](https://github.com/Alexio00/HEALTH/issues/87) | [Scheduler Launchers][RELEASE BLOCKER] Привязка scheduled jobs к принятому main SHA и legacy-pause gate | P0 Ops |
| [#82](https://github.com/Alexio00/HEALTH/issues/82) | [Scheduler Code][SECURITY] Heartbeat: исключить ложную свежесть от постороннего коммита | P1 Scheduler |
| [#75](https://github.com/Alexio00/HEALTH/issues/75) | [Research][Backlog] Аналоги персональной медкарты / мини-МИС и концепция HEALTH vNext | P4 Research |
| [#74](https://github.com/Alexio00/HEALTH/issues/74) | [Next iteration][Writer] Ошибки до исходного чата HEALTH, сверка статуса и handoff в HealthDB | P3 Writer next |
| [#69](https://github.com/Alexio00/HEALTH/issues/69) | Архитектура: стоит ли выносить другие компоненты HEALTH из main? | P3 Governance |
| [#65](https://github.com/Alexio00/HEALTH/issues/65) | [ARCHITECTURE][REQUIRED] Перенести SHEDULLER в один публичный HEALTH без утечки секретов и потери backup | P0 Ops |
| [#62](https://github.com/Alexio00/HEALTH/issues/62) | [Architecture][Backlog] Обязательная проверка совместимости изменений схемы Supabase с Writer, Validation и PWA | P1 Integration |
| [#61](https://github.com/Alexio00/HEALTH/issues/61) | [DOCS][REQUIRED] Русские пользовательские и эксплуатационные инструкции HEALTH | P1 Docs |
| [#58](https://github.com/Alexio00/HEALTH/issues/58) | [Backlog][Security] Дополнительная защита HEALTH PWA: MFA Supabase и приватность публикации Pages | P3 Security |
| [#57](https://github.com/Alexio00/HEALTH/issues/57) | [Backlog][FINAL CLEANUP] Ревизия веток HEALTH/SHEDULLER и временных файлов на двух Google Drives | P4 Hygiene |
| [#55](https://github.com/Alexio00/HEALTH/issues/55) | [Backlog][Portability] HEALTH для Claude, Qwen и других AI: безопасное чтение и Writer без прямого SQL | P4 Portability |
| [#54](https://github.com/Alexio00/HEALTH/issues/54) | [Backlog][Deployment automation] Максимальная автоматизация HUMAN_SETUP с обязательным ручным fallback каждого шага | P4 Automation |
| [#53](https://github.com/Alexio00/HEALTH/issues/53) | [Backlog][Deployment] Полный комплект инструкций для нового пациента: человек + AI, отдельная среда | P3 Deployment |
| [#52](https://github.com/Alexio00/HEALTH/issues/52) | [Backlog][Medical evidence] Полная инвентаризация и распознавание Sources, двусторонняя сверка REC и вопросов | P4 Private clinical |
| [#50](https://github.com/Alexio00/HEALTH/issues/50) | [REQUIRED NEXT WRITER] Независимый обязательный PWA scope-check (HIGH): временная приёмка 13.10.2026 | P0 Security (paused) |
| [#42](https://github.com/Alexio00/HEALTH/issues/42) | [Backlog] Полная сверка исторических вакцинаций из REC с планом | P4 Private clinical |
| [#41](https://github.com/Alexio00/HEALTH/issues/41) | [Backlog] Структурированная модель событий вакцинации и раздельные ссылки REC | P1 Integration |
| [#40](https://github.com/Alexio00/HEALTH/issues/40) | [Backlog] Единый реестр контрольных сроков и системные вопросы медицинской карты | P3 Plan/Questions |
| [#34](https://github.com/Alexio00/HEALTH/issues/34) | ChatGPT Writer gateway: авторизованный интерфейс записи без доступа модели к секретам | P1 Writer |
| [#19](https://github.com/Alexio00/HEALTH/issues/19) | Minor M-02: distinguish old 267-REC planning baseline from live 269 REC | P4 Historical |

## 4. Open HEALTH PR — all 24 (Draft at snapshot)

| PR | Target | Source branch | HEAD SHA | Candidate disposition — proposal only |
| --- | --- | --- | --- | --- |
| [#94](https://github.com/Alexio00/HEALTH/pull/94) | `scheduler-code` | `fix/scheduler-r5-b01-retired-zip-20261014` | `fa17f2f343e0733c8d864ab86a6f6b7cb21501d3` | Comparison to merged #96 before any close; no remerge |
| [#92](https://github.com/Alexio00/HEALTH/pull/92) | `main` | `docs/current-maintained-guides-20261014` | `cfd213fb992d61a1520e7426ce8797c81e2107ab` | Independently accepted exact HEAD, freeze; defer main release |
| [#89](https://github.com/Alexio00/HEALTH/pull/89) | `main` | `fix/scheduler-main-launcher-pins-20261014` | `724f8b500144c58887a2979d48264c8ab8607158` | Main launcher security fix; review with #72, #87 |
| [#88](https://github.com/Alexio00/HEALTH/pull/88) | `fix/scheduler-rclone-archive-pin-20261014` | `fix/scheduler-rotation-replay-20261014` | `84b8c37cfe41d3425d2b125649a787566936ec17` | Older stacked scheduler correction; compare to #95/#96 |
| [#86](https://github.com/Alexio00/HEALTH/pull/86) | `scheduler-code` | `docs/scheduler-operations-runbook-20261014` | `d7bab992a2895ff497cd602e2dc9941e80066a3b` | Operations runbook; align accepted Scheduler and live Ops |
| [#84](https://github.com/Alexio00/HEALTH/pull/84) | `writer-code` | `fix/writer-gateway-readiness-semantics-20261014` | `646625fbf9da62628d82386bde1c2987be45cd10` | Writer development in progress; coordinate with #35 |
| [#83](https://github.com/Alexio00/HEALTH/pull/83) | `main` | `docs/release-train-inventory-20261014` | `2209a604fdc9e640923bfbf0c602540cbef75d1c` | Roadmap and Issue #62 architecture docs; not a runtime release |
| [#81](https://github.com/Alexio00/HEALTH/pull/81) | `maintenance/scheduler-code-candidate-20261013` | `fix/scheduler-rclone-archive-pin-20261014` | `35218a67af482820ee83373e3a3fff3c60f6c931` | Old stacked scheduler archive-pin proposal; compare to accepted code |
| [#78](https://github.com/Alexio00/HEALTH/pull/78) | `main` | `security/trusted-pr-scope-20261014` | `b45260242c0a96bc032e63f3ece3307a8f21547d` | PAUSED security FAIL; no merge; HIGH #50 open |
| [#76](https://github.com/Alexio00/HEALTH/pull/76) | `main` | `maintenance/component-release-contract-20261014` | `fc3df598a5ffe4431c448b8151c9c2c669ffaaba` | Release/governance draft; current Rulesets/head drift requires reconciliation |
| [#72](https://github.com/Alexio00/HEALTH/pull/72) | `main` | `integration/scheduler-main-launchers-20261013` | `4d4659312cf89ad02b5e778b8c037db5c9e426e3` | Main launcher candidate; #87 release blockers, compare with #89 |
| [#71](https://github.com/Alexio00/HEALTH/pull/71) | `scheduler-code` | `automation/health-activity-main-20261013` | `ff7b957927e50973027ea63f642353a2dc69deb1` | Heartbeat proposal; compare to #82 and accepted scheduler-code |
| [#67](https://github.com/Alexio00/HEALTH/pull/67) | `main` | `feature/consolidate-scheduler-into-health-20261013` | `d4b811c48a82bcf752d5ab5f05d9d1b845583927` | Older consolidated Scheduler proposal; compare to current isolated design |
| [#64](https://github.com/Alexio00/HEALTH/pull/64) | `main` | `automation/health-activity-main-20261013` | `ff7b957927e50973027ea63f642353a2dc69deb1` | Older heartbeat proposal sharing branch with #71; compare before closing |
| [#60](https://github.com/Alexio00/HEALTH/pull/60) | `main` | `docs/audit-russian-consistency-20261013` | `6ee2f2879095e1a4254b7930903e6916cc9bce84` | Documentation overlaps accepted #92; compare before closure |
| [#59](https://github.com/Alexio00/HEALTH/pull/59) | `fix/vaccination-revaccination-case-20261013` | `feature/vax-combination-display` | `9b464e119f8e0d9d4e5ccac319a5bb5dec864027` | Legacy multivalent UI stacked on stale #51; blocked by canonical v2 schema |
| [#51](https://github.com/Alexio00/HEALTH/pull/51) | `pwa` | `fix/vaccination-revaccination-case-20261013` | `00b08f8fb8abe83d627ef2f4c71bb1b9f0755f8d` | Old Rv UI draft; accepted #80 supersedes by function, verify diff |
| [#45](https://github.com/Alexio00/HEALTH/pull/45) | `main` | `design/vaccination-registry-contract-20261013` | `0baadc31298afa885d0fb111fcbab308ece9b507` | Six-table v2 proposal; A62-C1 SQL/Writer integration not accepted |
| [#39](https://github.com/Alexio00/HEALTH/pull/39) | `main` | `docs/branch-routing-policy-20261013` | `6caaed181dacf2f8d38bbc8ffbefaf8f9df1809e` | Main routing/legacy Pages cleanup only in Writer SHA release window |
| [#36](https://github.com/Alexio00/HEALTH/pull/36) | `main` | `feature/supabase-test-consent-ui-20261013` | `8c8b6aa8840c33f3c8843cadf4030e0618a1940e` | OAuth test assets may already exist in pwa; confirm blobs, no main merge |
| [#35](https://github.com/Alexio00/HEALTH/pull/35) | `writer-code` | `feature/chat-writer-contract-20261013` | `bda786d72db54e08b9da949dcce3c9d54eb2a5b9` | Writer gateway contract overlap with #84; Writer team owns comparison |
| [#33](https://github.com/Alexio00/HEALTH/pull/33) | `main` | `maintenance/ru-governance-legacy-independence-20261013` | `063f1a581e2c549ead59e20689af70e9fcbf39a7` | Mixed governance/Writer/PWA docs; split before any main release |
| [#27](https://github.com/Alexio00/HEALTH/pull/27) | `main` | `migration/planned-medication-status` | `f866d4370af67645e1a2758e5a12a3104494bfd3` | Historical migration, live planned-status reconciled; do not replay |
| [#22](https://github.com/Alexio00/HEALTH/pull/22) | `main` | `test/nonmutating-probe-handoff` | `42251546d036a0ce9398592382f4a7e590fd5d9a` | Historical Docker/Work handoff; archive/keep decision later |

## 5. HEALTH branches — all 51

| Branch | Exact HEAD SHA | State / relation |
| --- | --- | --- |
| `automation/health-activity-main-20261013` | `ff7b957927e50973027ea63f642353a2dc69deb1` | open #71/#64 |
| `design/vaccination-registry-contract-20261013` | `0baadc31298afa885d0fb111fcbab308ece9b507` | open #45 |
| `docs/audit-russian-consistency-20261013` | `6ee2f2879095e1a4254b7930903e6916cc9bce84` | open #60 |
| `docs/branch-routing-policy-20261013` | `6caaed181dacf2f8d38bbc8ffbefaf8f9df1809e` | open #39 |
| `docs/current-maintained-guides-20261014` | `cfd213fb992d61a1520e7426ce8797c81e2107ab` | open #92 |
| `docs/pwa-independent-release-20261014` | `2460a217c65d523304af2135f2fdf5a181910eb3` | no open PR — inspect, no automatic delete |
| `docs/release-train-inventory-20261014` | `2209a604fdc9e640923bfbf0c602540cbef75d1c` | open #83 |
| `docs/scheduler-operations-runbook-20261014` | `d7bab992a2895ff497cd602e2dc9941e80066a3b` | open #86 |
| `feature/chat-writer-contract-20261013` | `bda786d72db54e08b9da949dcce3c9d54eb2a5b9` | open #35 |
| `feature/consolidate-scheduler-into-health-20261013` | `d4b811c48a82bcf752d5ab5f05d9d1b845583927` | open #67 |
| `feature/pwa-frontend-improvements-20261013` | `a4c54bcb027084d8127582aebafdaf81463ae7ae` | no open PR — inspect, no automatic delete |
| `feature/pwa-vaccination-multi-infection-display-20261014` | `accb4e50db1bd4269ee10f606e6143c86d903c3d` | merged PR branch retained — cleanup candidate |
| `feature/supabase-test-consent-ui-20261013` | `8c8b6aa8840c33f3c8843cadf4030e0618a1940e` | open #36 |
| `feature/test-consent-bootstrap-20261013` | `83233cc73aa87f982250c464bb17750e4967ba67` | no open PR — inspect, no automatic delete |
| `feature/test-email-password-recovery-20261013` | `acbdd62411238604d2c46fc6ed8d32c0c208771c` | no open PR — inspect, no automatic delete |
| `feature/test-exact-oidc-scopes-20261013` | `d1094fb5dbc2e0d1b1f751cf01eb23051199b092` | no open PR — inspect, no automatic delete |
| `feature/vax-combination-display` | `9b464e119f8e0d9d4e5ccac319a5bb5dec864027` | open #59 |
| `feature/writer-browser-exact-consent-20261014` | `acf8593421e2199b52300b03d41e23e239017351` | merged PR branch retained — cleanup candidate |
| `fix/pwa-rv-stage-clean-20261014` | `8ef8febe7e62f62b39a2bc5fb2461f06c008ea9a` | merged PR branch retained — cleanup candidate |
| `fix/scheduler-activate-done-revalidation-20261014` | `09e0ff0a9f6f33780a07eaabc4087a2b094e10ef` | no open PR — inspect, no automatic delete |
| `fix/scheduler-main-launcher-pins-20261014` | `724f8b500144c58887a2979d48264c8ab8607158` | open #89 |
| `fix/scheduler-r5-b01-retired-zip-20261014` | `fa17f2f343e0733c8d864ab86a6f6b7cb21501d3` | open #94 |
| `fix/scheduler-r5-journal-replay-20261014` | `d6c08858f302f3b5ee296aa5c2dc9d6f0ffd7c73` | no open PR — inspect, no automatic delete |
| `fix/scheduler-r5b-preflight-order-20261014` | `9afe2ab709f85d2f0b4aa0155782f7191099bbd4` | merged PR branch retained — cleanup candidate |
| `fix/scheduler-rclone-archive-pin-20261014` | `35218a67af482820ee83373e3a3fff3c60f6c931` | open #81 |
| `fix/scheduler-rotation-replay-20261014` | `84b8c37cfe41d3425d2b125649a787566936ec17` | open #88 |
| `fix/test-oauth-opaque-id-20261013` | `a25aecaf0878c724374d6d1ed2a2e05921b796de` | no open PR — inspect, no automatic delete |
| `fix/vaccination-revaccination-case-20261013` | `00b08f8fb8abe83d627ef2f4c71bb1b9f0755f8d` | open #51 |
| `fix/writer-gateway-readiness-semantics-20261014` | `646625fbf9da62628d82386bde1c2987be45cd10` | open #84 |
| `frontend/vaccination-overview-20261013` | `e16f893ccef9645386904cdeb602d315af15eabc` | no open PR — inspect, no automatic delete |
| `integration/scheduler-main-launchers-20261013` | `4d4659312cf89ad02b5e778b8c037db5c9e426e3` | open #72 |
| `integration/scheduler-r5b01-on-accepted-r5ab-20261014` | `bdad33b9a76f0b0b1fb595c0d67d42322c6d8339` | merged PR branch retained — cleanup candidate |
| `main` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | accepted production Writer SHA |
| `maintenance/component-release-contract-20261014` | `fc3df598a5ffe4431c448b8151c9c2c669ffaaba` | open #76 |
| `maintenance/frontend-accordion-medrec-visits-20261013` | `d682363315703e94693aeea4807adf5fd77ecc7c` | no open PR — inspect, no automatic delete |
| `maintenance/pwa-deploy-gate-20261013` | `855f2a44fa8bc4039d21a605a39513bde7594262` | no open PR — inspect, no automatic delete |
| `maintenance/pwa-release-observability-20261013` | `681a5e2c4ad8f9380c27359d0fecda49fa5dfe32` | no open PR — inspect, no automatic delete |
| `maintenance/pwa-release-safety-20261013` | `6acadf2732a672e8a2af6b80c161952cfe618683` | no open PR — inspect, no automatic delete |
| `maintenance/pwa-ui-refine-20261007` | `717dc547e15f3a86e6733e0084bac403167e330d` | no open PR — inspect, no automatic delete |
| `maintenance/ru-governance-legacy-independence-20261013` | `063f1a581e2c549ead59e20689af70e9fcbf39a7` | open #33 |
| `maintenance/scheduler-code-candidate-20261013` | `f8a4acc582e94f665fb58e840db7769c8e936553` | no open PR — inspect, no automatic delete |
| `migration/planned-medication-status` | `f866d4370af67645e1a2758e5a12a3104494bfd3` | open #27 |
| `pwa` | `c97bb4fc3d9bdf4321a360c437a1460a9b06e1bc` | published PWA |
| `release/pages-ui-20261013-preserve-oauth-test` | `e55aea6f00e6130de2dcdcc57aed938de478b93b` | no open PR — inspect, no automatic delete |
| `scheduler` | `98f9c41ff9b1496dfc40d0da960971ae7bf58a42` | heartbeat only |
| `scheduler-code` | `0f071b3061d7c3f53b9e637a071b3a2af95d761f` | Scheduler development only |
| `security/trusted-pr-scope-20261014` | `b45260242c0a96bc032e63f3ece3307a8f21547d` | open #78 |
| `test/nonmutating-probe-handoff` | `42251546d036a0ce9398592382f4a7e590fd5d9a` | open #22 |
| `test/pwa-protection-smoke-20261013` | `6aa81a96e44033366c2cdafc7a4b6622f676432a` | no open PR — inspect, no automatic delete |
| `test/trusted-scope-r2-fixtures-20261014` | `09c6a9f663e09ba5b4d82503b3d17d15b62cd916` | no open PR — inspect, no automatic delete |
| `writer-code` | `7d67ae96b8f8e344321a4df87e467fff71a20652` | Writer development only |

## 6. SHEDULLER private inventory summary and gates

At this snapshot old `Alexio000/SHEDULLER` still has **5 Issues, 13 PR and 15 branches**. Do not list its private feature paths/Issue descriptions, Source/Drive details or secrets in this public GitHub artifact. A separately maintained private inventory must distinguish live backup/keepalive, Writer OAuth/MCP exploratory branches, governance backup, historical full migration/recovery candidates and deferred minor findings. The repo is **not** disposable yet; stop, archive/delete, transfer of credentials or Source-related operations each require separate Owner GO.

## 7. Untracked or only partly tracked concrete follow-ups (do not create excess Issues automatically)

| ID | Scope | Owner / acceptance |
| --- | --- | --- |
| GAP-01 | **Manual production PWA authorized-session smoke** on exact accepted #85 release: login, intended read-only sections, 1/2 controls without capturing clinical data or Secrets. Technical HTTP/full-byte postcheck is PASS; this manual check remains NOT RUN. | Owner + PWA QA, limited private report; no new #85 audit |
| GAP-02 | **Historical private document locator exposure** in older public #45 commit/PR history, although current HEAD has no locator. | Owner decides incident scope/history/caches and remediation; never echo URL; avoid destructive force-push without explicit approval |
| GAP-03 | **Single release order/pin synchronization checklist:** resolve which docs/governance/main launcher PRs are included together, what is retained, and how Writer is reaccepted while backup remains safe. | Architecture + Ops + Owner. This roadmap is advisory, not signed manifest |
| GAP-04 | **Approved cleanup disposition** of orphan branches and overlapping PRs based on exact diff, merged ancestry, remaining dependencies and recoverability. | #57; no automatic delete or PR closure |
| GAP-05 | **GitHub schedule silence detection residual risk**: internal scheduled checks cannot self-report simultaneous total schedule failure; owner selected manual monitoring, not another paid/external watchdog. | #65/#82 operations runbook, recorded residual risk, not automatic new service |

## 8. Teams to assign without duplicating Writer

- **Writer**: ALREADY BUSY. No second Writer team or broad rewrite. Consume its current #34/#62 candidate on handoff.
- **Scheduler Operations existing chat**: read-only operational readiness & trust boundary; do not execute cutover.
- **PWA documentation team**: narrow independent `pwa` documentation Draft PR; no executable changes and no merging.
- **Repo hygiene auditor**: independent read-only branch/PR graph and proposed keep/close/archive matrix across two repos; private details only in private report.
- **Deployment manual runbook team**: #53 conditional as-is/target, one patient one instance, no account creation or automation; #54 remains later.
- **Optional research team**: #75 vNext/PHR competitive review, lower priority; no clinical data, no greenfield rewrite approval.

## 9. Completion contract

For each independently delivered package: compare exact current BASE/HEAD and full diff, cite audit/negative tests, mark PASS/FAIL/NOT RUN, identify protected scopes and rollback, report live rulesets and open review threads, request separate Product Owner GO for technical merge and **separate** clinical or production change GO where appropriate. Release verdicts and production activation must never be inferred from a merged development PR or all-green CI.

**No actual production schema, Writer, PWA, Scheduler cutover, Source or backup operation is authorized by this document.**
