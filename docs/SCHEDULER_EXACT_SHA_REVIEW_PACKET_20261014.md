# Scheduler HEALTH — пакет независимого exact-SHA review (14.10.2026)

**Статус: REVIEW PREPARATION / NO-GO, не независимое аудиторское заключение.**
Product Owner выбрал временный **ручной эксплуатационный контроль** без внешнего watchdog. Это не заменяет отдельного owner GO на технический merge или запуск Scheduler/backup.

## 1. Замороженные кандидаты и diff на момент подготовки

| Компонент | Target | BASE_SHA (40) | HEAD_SHA (40) | Diff |
|---|---|---|---|---|
| [PR #73](https://github.com/Alexio00/HEALTH/pull/73): исторический executable candidate | `scheduler-code` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | `f8a4acc582e94f665fb58e840db7769c8e936553` | Superseded составным #90; не сливать как второй выпуск |
| [PR #72](https://github.com/Alexio00/HEALTH/pull/72): старый launcher candidate | `main` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | `4d4659312cf89ad02b5e778b8c037db5c9e426e3` | 5 новых workflow; **не выпускать совместно с #89** |
| [PR #89](https://github.com/Alexio00/HEALTH/pull/89): исправленный кандидат trusted default-main launchers | `main` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | `724f8b500144c58887a2979d48264c8ab8607158` | Те же 5 workflow; отдельно от #72 добавлены main SHA/pause/preflight gates и архивный rclone SHA-256 в трёх jobs; самостоятельная приёмка обязательна |
| [PR #81](https://github.com/Alexio00/HEALTH/pull/81) → [#88](https://github.com/Alexio00/HEALTH/pull/88): историческая stacked цепочка | `scheduler-code` через feature branches | `f8a4acc582e94f665fb58e840db7769c8e936553` → `35218a67af482820ee83373e3a3fff3c60f6c931` | `84b8c37cfe41d3425d2b125649a787566936ec17` | #88 получил независимый FAIL при повторном activate/DONE; сохраняется история, но не GO |
| [PR #90](https://github.com/Alexio00/HEALTH/pull/90): текущий объединённый Scheduler Code | `scheduler-code` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | `09e0ff0a9f6f33780a07eaabc4087a2b094e10ef` | 37 файлов vs base; +3 файла относительно #88, из них 2 изменены, 1 добавлен. CI success, самостоятельный независимый review ещё требуется; #82 не исправлен |
| [PR #86](https://github.com/Alexio00/HEALTH/pull/86): this documentation | `scheduler-code` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | **moving HEAD, fetch again** | documentation only, **не часть** frozen #73 code review |

На дату среза `HEALTH/main` = `3409791f1ffc5749020e7ff07139b0cec722f6fc`, то же значение в действующем приватном State как accepted Writer code SHA. `HEALTH/scheduler-code` = этот же базовый SHA; `HEALTH/scheduler` = `98f9c41ff9b1496dfc40d0da960971ae7bf58a42`. `SHEDULLER/main` = `8656a360c2b24c0f51e6e2b80edf78e6bd89ccc4` — текущий исполнитель backup. Подтвердить повторно непосредственно перед review/merge.

### Проверяемые границы diff

- #73: `.github/workflows/health-scheduler-validation.yml` — **только** synthetic CI, без расписания/production secrets; `scripts/scheduler/**`, `scripts/automation/**`, `docs/HEALTH_ACTIVITY_RU.md`, `docs/SCHEDULER_CONSOLIDATION_RU.md`. Production launcher не должен появляться в `scheduler-code` после изменения HEAD.
- #72: **строго** `.github/workflows/health-activity.yml`, `health-backup-preflight.yml`, `health-backup-release.yml`, `health-complete-backup.yml`, `health-supabase-keepalive.yml`. Любая модификация `code-validation.yml`, Writer/Supabase/PWA или scope-check относительно frozen diff требует остановить review и новую отдельную оценку.
- Старые PR #64/#71 — исторические кандидаты, их workflow не добавлять повторно. Совмещать эти PR с #72/#73 нельзя.
- У `scheduler` нет branch protection на дату среза. У Ruleset `Protect Scheduler Code` active есть deletion/non-fast-forward/PR, но **нет** обязательного `required_status_checks`. Это отдельный security risk, ручной review остаётся главным gate.

## 2. Тестовый план независимого аудитора

Отдельный независимый reviewer, а не автор кода или этот эксплуатационный пакет, воспроизводит следующие действия. Выполнять только на **точном frozen HEAD**, без production Secrets и без подключения к реальной медицинской БД.

### A. Source & scope provenance

1. Установить `BASE_SHA`, `HEAD_SHA`, целевую ветку, все файлы diff, status/changes/renames, фактический Ruleset. Сверить HEAD перед каждым вердиктом.
2. `git diff --name-status -M BASE_SHA HEAD_SHA`, `git diff --check BASE_SHA HEAD_SHA`. Проверить отсутствие подозрительных binary/symlink, скрытых credential/source references, подмены проверки, двойных расписаний.
3. Сверить собственный CI код с тем, что реально исполнялось; зелёный `health-scheduler-validation.yml` не независимый security issuer.
4. Для #73 проверить тестовый run [38549825326](https://github.com/Alexio00/HEALTH/actions/runs/38549825326): synthetic success на `f8a4acc5...`, **не** реальный restore proof и не владелец GO.

### B. Синтетика итогового Scheduler Code (#90; предшественники #73/#81/#88 — только provenance)

- `python3 -m compileall -q scripts/scheduler scripts/automation`;
- `python3 scripts/validation/public_secret_guard.py`;
- `python3 -m unittest discover -v -s scripts/automation -p test_scheduler_transfer.py`;
- `python3 scripts/scheduler/test_complete_archive.py -v`;
- `python3 scripts/scheduler/test_complete_payload.py -v`;
- `python3 scripts/scheduler/test_complete_sources.py -v`;
- `python3 scripts/scheduler/test_complete_restore.py -v`;
- `python3 scripts/scheduler/test_candidate_provenance.py -v`;
- `python3 scripts/scheduler/test_scheduler_reconciliation.py -v`;
- `python3 scripts/scheduler/test_cutover_guard.py -v`;
- `python3 scripts/scheduler/test_drive_rotation.py -v`;
- `node --test scripts/automation/health_activity.test.mjs`.

Все без реальных credential; нужны синтетические fixture identifiers. Точный набор команд взят из frozen synthetic workflow и должен быть пересмотрен при смене HEAD.

Проверить отрицательные сценарии: неверный producer/issuer pin, unknown ACTIVE или foreign CANDIDATE, dropped upload response, incomplete orphan, lost marker PATCH, duplicate rotation, fail-held Writer lock, missing Auth/role/Source digest в восстановлении. Новая доработка #82 должна независимо доказать, что посторонний commit в `scheduler` **не** сбрасывает heartbeat freshness и что overdue remediation/email semantics определены. Отсутствие этих доказательств = NOT_VERIFIED/NO-GO, даже если исходные тесты зелёные.

### C. Main launchers (#72)

1. Для каждого из пяти workflows проверить `on`, `if`, `concurrency`, `permissions`, `environment`, `secrets`, входные переменные, full pinned SHA и фактический trusted `main` trust source.
2. Все secret-consuming/branch-write jobs должны fail closed на **непринятый launcher/main SHA**, а не только на правильный `scheduler-code` checkout. Актуальная [Issue #87](https://github.com/Alexio00/HEALTH/issues/87): этот gate отсутствует у daily backup, keepalive/heartbeat/preflight. Нельзя заявить PASS до исправления и негативных тестов.
3. Daily backup обязан отказывать при возобновившемся legacy SHEDULLER; owner-set `HEALTH_LEGACY_BACKUP_PAUSED=true` не доказывает zero-in-flight и нужен независимый readback. `health-backup-release.yml` имеет больше gate, но не делает daily безопасным автоматически.
4. Проверить, что checkout `refs/heads/scheduler-code` используется только для ancestry test принятого pin, а не для исполнения moving HEAD; GitHub token `contents:write` выдаётся на repository, не только на `scheduler`. `HEAD:refs/heads/scheduler` в JS — намерение, не достаточное permission boundary.
5. Release `workflow_dispatch`: режимы `candidate`, `activate`, `quarantine-orphan`; correct actor, manual ACK, accepted main, producer SHA, private environment, exact archive SHA256, no unreviewed logs/artifacts/Drive IDs.
6. Проверить реальные ограничения GitHub personal/public/free (Environment approval/secrets, Rulesets, status issuer). Не считать существование YAML доказательством настроенного Environment; ручная exact-SHA приёмка временно допустима, HIGH #50 остаётся OPEN.
7. Назначить owner-approved rollback: если новый backup не подтверждён, никакой повторный Trash; reconcile CANDIDATE/UPLOADING/journal перед возвратом SHEDULLER. Writer после restore оставлять disabled до отдельного принятия.

## 3. Gate matrix

| Gate | Статус на дату документа | Нужное доказательство | Кто принимает |
|---|---|---|---|
| #90 fixed SHA & diff | VERIFIED metadata | Полный составной diff от protected scheduler-code, независимый code/privacy/security review; не переносить FAIL/PASS с #88 | Независимый reviewer |
| #90 synthetic CI | CI PASS: 38589627931 | Воспроизведённые отрицательные случаи ротации DONE, включая old SHA/Trash/ACL drift, и отдельное исправление #82 | Reviewer, не GitHub CI |
| #90 accepted merge | NO-GO | Независимый PASS именно #90 или более нового HEAD + отдельный owner GO, re-read Rulesets/HEAD; #82 блокирует release | Owner |
| #89 five workflows | VERIFIED metadata / SYNTHETIC CHECKS ONLY | Exact independent review `if/on`/secret/accepted-main/pause/rollback; rclone SHA variable в трёх jobs передаётся, но значение не утверждено и Environment не проверен; #87 нельзя объявлять исправленным по локальному тесту | Reviewer |
| #89 merge into Writer main | NO-GO | Выбор единственного launcher train (#89 vs #72), accepted Writer main SHA/broker/runtime reacceptance, owner GO | Owner + Writer coordinator |
| HEALTH scheduler production activation | NO-GO | Установленные permission boundaries, private proof of complete restore, legacy paused & idle, cutover runbook, separate GO | Owner + architecture coordinator |
| Two observed new scheduled runs | NOT_PERFORMED | Реальные production runs после принятия + proof ACTIVE/restore | Operations |
| Full silence notifications | NOT_AUTOMATED | Временный ручной контроль; внешнего watchdog нет | Operations |
| HIGH #50 independent trusted issuer | OPEN | Не подменять ручной процедурой результат security review; задача остаётся в backlog | Architecture coordinator |

### Меняется HEAD = меняется review

Каждый новый commit в #73/#81/#88 или #89 аннулирует прежний exact-SHA вердикт. Документационный #86 должен быть согласован по порядку merge с #73/#81/#88: изменение базовой `scheduler-code` ветки изменяет сравнение файлов и требует повторного readback, даже если конкретный старый кодовый HEAD не изменился. Изменение `main`, **включая документацию**, меняет принятый Writer SHA и требует отдельного согласования. Merge #73 в `scheduler-code` не равен активации backup. Merge #72 в `main` не равен production GO.

## 4. Форма отчёта независимой приёмки

```text
Component: scheduler-code | main-launchers
Repo/target:
BASE_SHA (40):
HEAD_SHA (40):
Review UTC:
Reviewer independent of author: YES / NO / NOT_VERIFIED
Changed paths + full diff checksum:
Rulesets + required statuses:
Code/security/privacy negative tests executed (exact commands):
Synthetic results + evidence URLs:
Cross-component checks (Writer lock, backup/restore, Secrets/Environment):
Open HIGH/MEDIUM findings:
Rollback procedure and constraints:
Verdict: EXACT_SHA_REVIEW_PASS | EXACT_SHA_REVIEW_FAIL | NOT_VERIFIED
Owner explicit GO for this exact SHA: YES | NO
Release status: DRAFT / ACCEPTED_CODE / PRODUCTION_VERIFIED
```

Не утверждать `REVIEW_PASS` по одному только этому пакету, GitHub CI или read-only осмотру реализации. Private data/restore evidence передавать исключительно в разрешённом приватном контуре; здесь хранить только неприватные идентификаторы/хеши и факт проверки.

## 5. Cutover — только после нового решения Owner

1. После исправления открытого #82 и полного независимого security/recovery review принять **один** итоговый executable release SHA #90 (либо новый HEAD, прошедший повторную проверку), без изменения `scheduler`; подтвердить отсутствие production launchers в кодовой ветке. Не делать дополнительные merge исторических #73/#81/#88.
2. Для #89 проверить устранение #87 и совместимость независимого rclone archive SHA из #90; повторить exact-SHA review каждого изменённого кандидата. Предыдущий independent FAIL #88 не переопределять.
3. Согласовать единственного launcher-кандидата **#89 вместо #72** или другой отдельно утверждённый final head. Для актуального #89 передача `${{ vars.HEALTH_RCLONE_ARCHIVE_SHA256 }}` в три workflow уже присутствует (HEAD `724f8b500144c58887a2979d48264c8ab8607158`); до независимой приёмки необходимо документировать независимый источник и утверждение **самого значения** SHA-256 для rclone v1.75.1, область доступности Variable для `health-private-backup` и `health-private-recovery`, negative tests absent/wrong digest и отсутствие обходного same-origin checksum. Затем отдельное принятие `main` с новым Writer SHA и broker/runtime validation; **все новые расписания выключены**.
4. Проверить restricted roles/Secrets/private Environments (только существование/доступ/полномочия, не выводить значения) и independent full recovery.
5. Получить отдельное owner GO: остановить SHEDULLER schedules и дождаться завершения всех jobs **до первой новой записи в shared backup**; подтвердить отсутствие чужого CANDIDATE/UPLOADING.
6. Owner-only candidate/review/activate exact digest; после запуска HEALTH schedule подтвердить два подряд реальных scheduled backup с независимой проверкой. Не удалять SHEDULLER/старые архивы без отдельного решения владельца.

Связанные Issues: [#65](https://github.com/Alexio00/HEALTH/issues/65), [#82](https://github.com/Alexio00/HEALTH/issues/82), [#87](https://github.com/Alexio00/HEALTH/issues/87), [#50](https://github.com/Alexio00/HEALTH/issues/50).
