# Scheduler HEALTH — пакет независимого exact-SHA review (14.10.2026)

**Статус: REVIEW PREPARATION / NO-GO, не независимое аудиторское заключение.**
Product Owner выбрал временный **ручной эксплуатационный контроль** без внешнего watchdog. Это не заменяет отдельного owner GO на технический merge или запуск Scheduler/backup.

## 1. Замороженные кандидаты и diff на момент подготовки

| Компонент | Target | BASE_SHA (40) | HEAD_SHA (40) | Diff |
|---|---|---|---|---|
| [PR #73](https://github.com/Alexio00/HEALTH/pull/73): executable code + nonsecret tests | `scheduler-code` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | `f8a4acc582e94f665fb58e840db7769c8e936553` | 34 added files, 67 commits vs base |
| [PR #72](https://github.com/Alexio00/HEALTH/pull/72): старый launcher candidate | `main` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | `4d4659312cf89ad02b5e778b8c037db5c9e426e3` | 5 новых workflow; **не выпускать совместно с #89** |
| [PR #89](https://github.com/Alexio00/HEALTH/pull/89): исправленный кандидат trusted default-main launchers | `main` | `3409791f1ffc5749020e7ff07139b0cec722f6fc` | `82c6d75ee839ee766896fed817712459733680a1` | Те же 5 workflow + 4 точечных исправления относительно #72; отдельная приёмка обязательна |
| [PR #81](https://github.com/Alexio00/HEALTH/pull/81) → [#88](https://github.com/Alexio00/HEALTH/pull/88): stacked Scheduler Code | `scheduler-code` через зависимые feature branches | `f8a4acc582e94f665fb58e840db7769c8e936553` → `35218a67af482820ee83373e3a3fff3c60f6c931` | `84b8c37cfe41d3425d2b125649a787566936ec17` | Исправления доверенного rclone-архива и повторной ротации; итоговый combined diff ещё требует независимого review |
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

### B. Синтетика Scheduler Code (#73 и последующие исправления)

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
| #73 fixed SHA & diff | VERIFIED metadata | Статический независимый code/privacy/security review на этот SHA | Независимый reviewer |
| #73 synthetic CI | CI PASS | Воспроизведённый независимый негативный набор, включая #82 | Reviewer, не GitHub CI |
| #73 accepted merge | NO-GO | Reviewer PASS + отдельный owner GO + re-read Rulesets/HEAD | Owner |
| #89 five workflows | VERIFIED metadata / SYNTHETIC CHECKS ONLY | Exact independent review `if/on`/secret/accepted-main/pause/rollback, cross-PR rclone SHA pin; #87 нельзя объявлять исправленным по локальному тесту | Reviewer |
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

1. Отдельно принять executable release SHA #73, без изменения `scheduler`; подтвердить отсутствие новых workflow в кодовой ветке.
2. Исправить #82/#87, затем повторить exact-SHA review соответствующих изменённых кандидатов.
3. Согласовать единственного launcher-кандидата **#89 вместо #72** или другой отдельно утверждённый final head. До независимой приёмки обеспечить совместимость с итоговым `install_rclone.sh` из #81/#88: `HEALTH_RCLONE_ARCHIVE_SHA256` должен иметь независимо принятую контрольную сумму и передаваться трем workflow, которые его вызывают. Затем отдельное принятие `main` с новым Writer SHA и broker/runtime validation; **все новые расписания выключены**.
4. Проверить restricted roles/Secrets/private Environments (только существование/доступ/полномочия, не выводить значения) и independent full recovery.
5. Получить отдельное owner GO: остановить SHEDULLER schedules и дождаться завершения всех jobs **до первой новой записи в shared backup**; подтвердить отсутствие чужого CANDIDATE/UPLOADING.
6. Owner-only candidate/review/activate exact digest; после запуска HEALTH schedule подтвердить два подряд реальных scheduled backup с независимой проверкой. Не удалять SHEDULLER/старые архивы без отдельного решения владельца.

Связанные Issues: [#65](https://github.com/Alexio00/HEALTH/issues/65), [#82](https://github.com/Alexio00/HEALTH/issues/82), [#87](https://github.com/Alexio00/HEALTH/issues/87), [#50](https://github.com/Alexio00/HEALTH/issues/50).
