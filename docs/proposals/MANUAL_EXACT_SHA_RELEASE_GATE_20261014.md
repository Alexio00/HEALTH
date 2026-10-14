# HEALTH — ручной release gate по точному SHA (решение владельца принято)

**Дата решения:** 14.10.2026. **Статус:** владелец утвердил ручную независимую приёмку; действующая процедура закреплена в приватных HealthDB Project Manual (раздел 18) и Project State. Этот файл остаётся техническим отражением решения внутри **Draft PR #76**; он не входит в принятый `main` и не разрешает его merge, медицинскую запись, изменение GitHub Rulesets, Writer либо Supabase. HIGH Issue #50 остаётся OPEN.

## Почему вместо автоматического trusted PR-check

Независимые аудиты R1, R2 и R3 для Draft #78 признали вариант `pull_request_target` + собственный Python checker **неготовым к security release**:
- R3 exact SHA `b45260242c0a96bc032e63f3ece3307a8f21547d`: Python compilation PASS, unit 25/25 PASS, исходные 66 R2 probes повторены; 125 дополнительных выявили 7 неожиданных ACCEPT (2 оставшихся LOW gaps типов metadata). Исходный R3-отчёт предоставлен владельцем как локальные пути; полный текст и evidence ZIP не получены этим техническим чатом и не проверены самостоятельно.
- **HIGH #50-1:** статус GitHub Actions App и одинаковое имя job не идентифицируют конкретный trusted workflow, допускается сценарий impersonation кандидатной проверкой (реальные merge-block tests не выполнялись).
- **HIGH #50-2:** workflow из изменяемого default `main` способен не исполнять собственную самопроверку; отдельная неизменяемая гарантия issuer отсутствует.
- GitHub документирует source-specific `Require workflows to pass before merging` как правило **organization/enterprise**, не подтверждённое для personal/public/free: https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

**Решение владельца принято:** перейти к owner-controlled manual acceptance, прекратить циклическое исправление LOW в #78 ради автоматического rollout. Держать #78 Draft/PAUSED без merge, HIGH #50 OPEN с остаточным риском. Возврат к автоматизации требует отдельного решения и доказательства source-specific mandatory issuer.

## Минимальный gate без новых сервисов

1. **Freeze exact commit:** определить `repo`, целевую ветку, полный 40-символьный `HEAD_SHA`, `BASE_SHA`, все изменённые файлы и точный diff. Никаких moving refs (имя ветки, `HEAD`, mutable tag) в качестве утверждённого исполняемого кода. Провести readback непосредственно перед выпуском.
2. **Независимый технический review:** отдельный проверяющий без доступа к изменению кандидата подтверждает exact SHA, синтетические тесты, запрет Secrets/medical data, границы изменения, отрицательные сценарии по рискам, rollback. Evidence хранится в разрешённом приватном техническом контуре; в публичный GitHub — только безопасный текстовый итог и несекретные хеши.
3. **Owner release decision:** владелец читает точный diff/evidence и отдельно подтверждает *именно* `repo + BASE_SHA + HEAD_SHA + component + scope + GO/NO-GO`. Комментарий владельца в PR может фиксировать это решение, **но не является криптографической подписью и не становится автоматически обязательным правилом GitHub**. Не использовать фразу `signed consent` к медицинским операциям для GitHub PR.
4. **Manual merge checkpoint:** перед merge снова сравнить PR HEAD/base, unresolved threads, статус Ruleset и source CI; при любом изменении SHA/диффа/требований прежнее решение аннулируется. Green CI — дополнительный сигнал, не независимая security аттестация. Релиз выполнять только владельцу после решения; нельзя включать auto-merge или допускать ChatGPT-triggered merge.
5. **Postrelease check / rollback:** прочитать фактический merge/release SHA и функционально проверить запущенный компонент; сохранить результат. Если отказ — остановить выпуск и использовать согласованный rollback (новый commit/revert/предыдущий immutable component release). `reset --hard`/force push защищённых веток недопустимы. `main` revert порождает **новый** Writer SHA и требует штатной повторной приёмки.

## По компонентам

| Направление | Разработка | Что реально можно выпускать сейчас |
|---|---|---|
| `pwa` | PR к `pwa` и действующие Pages workflows | Отдельная ручная приёмка exact PWA SHA, существующий required `static` оставить; независимый review каждого release-sensitive диффа + браузерная постпроверка |
| `scheduler-code` | PR к `scheduler-code`; `scheduler` только heartbeat | Проверенный и утверждённый candidate code SHA, но НЕ активация schedule/backup до принятия runtime launcher и полного restore/backup gate |
| `writer-code` | PR к `writer-code` с действующим protected Ruleset | Только стадия разработки; НИКАКОГО нового медицинского Writer runtime без его отдельной independent review, exact signed owner authorization, broker/runtime policy и recovery acceptance |
| `main` | Минимальный доверенный control plane, принятие отдельно | Существующая модель Writer `HEALTH_WRITER_ACCEPTED_SHA == main/github.sha == health_writer.runtime_policy.code_sha` действует; всякий новый main commit, включая docs-only, требует предусмотренного change-control/reacceptance |

Нельзя приравнивать ручное одобрение GitHub PR к медицинскому owner intent или независимой source/semantic проверке Writer. Медицинский single-writer/SQL exclusion и принятый bounded Writer остаются неизменны.

## Принятие и границы

**Вариант А утверждён владельцем 14.10.2026.** Процедура введена в управляющие Project Manual/State. Автоматический кандидат #78 приостановлен, но не объявлен безопасным и не слит. Изменения в GitHub PR и документах не являются новым кодовым или production release.

**Следующий выпуск:** выбрать конкретный PWA-only PR-кандидат, сделать независимую проверку exact SHA, получить отдельно явно подтверждённый owner GO для этого кандидата, затем повторить readback и выполнить release/postcheck. Не использовать это общее решение как одобрение конкретных PR #35/#73/#77/#72/#76. Новый Writer release/production `main` требует собственной технической и эксплуатационной приёмки и отдельной авторизации.

GitHub Rulesets, Secrets, `main`, Writer runtime, Google Drive Sources и Supabase не меняются этой процедурой. При проверенном отсутствии независимого обязательного issuer не заявлять, что ручное решение делает merge технически невозможным.
