# HEALTH Writer — защищённое подтверждение точного кандидата в браузере

**Статус:** STAGED DESIGN / SYNTHETIC POLICY ONLY / SECURITY RELEASE NO-GO
**Дата решения владельца:** 14.10.2026
**Режим:** maintenance, без медицинских данных, без production-развёртывания
**Целевая ветка:** `writer-code` через изолированный PR
**Production Writer:** прежний принятый `main` SHA `3409791f1ffc5749020e7ff07139b0cec722f6fc`, без изменений

## 1. Принятое решение

Владелец подтвердил отдельную защищённую страницу для явного подтверждения **каждого** медицинского кандидата. Это техническое согласие со способом подтверждения, **не согласие на какую-либо конкретную медицинскую запись, миграцию, SQL/Secrets, развёртывание или merge**.

На первом этапе применяется дополнительная браузерная проверка только **точного кандидата** (`kind=candidate`), а не автоматическая замена действующего GitHub OIDC-владельческого механизма. Для первичного `intent` остаётся отдельная авторизация согласно действующему Writer. Новая модель владельческого `intent` требует самостоятельного принятия.

## 2. Архитектура без нового платного сервиса

1. Использовать существующий Supabase проект, Supabase Auth и **предлагаемую** ограниченную Edge Function. Новых баз данных, GitHub Secrets в браузере, публичного SQL и параллельного Writer не требуется.
2. Отдельная защищённая страница предъявляет владельцу **server-rendered** точный before/after и основание. Ни ChatGPT, ни браузер не могут заменить содержание review. Текущую read-only PWA не менять в этом Writer-кандидате.
3. Auth идентифицирует пользователя, **но не является сам по себе consent**. Server проверяет подписанный JWT через поддерживаемый Supabase Auth способ, текущую действительность сессии (`session_id` в `auth.sessions`) и отдельный приватный allowlist реального владельца. Наличие строки в `app_readers` означает право чтения, не право согласования.
4. Серверный challenge привязан к `owner_uid`, `session_id`, `request_key`, `candidate_sha`, `before_sha`, `after_sha`, `review_sha`, `accepted_sha`; содержит случайный одноразовый nonce **только в виде SHA-256** в приватном хранилище; TTL не больше 5 минут. Сам nonce выдаётся лишь доверенному браузеру в защищённом ответе, **не помещается в URL**, публичные логи или GitHub.
5. Страница отображает клиническую разницу и однозначные действия **Подтвердить** / **Отклонить**. Подтверждение требует фактического действия в этой странице; GET, prefetch, наличие Auth-сессии или текст ChatGPT не могут инициировать approval. Браузер передаёт только `challenge_id`, nonce, увиденный `review_sha`, `decision`.
6. Edge Function перед решением перечитывает действующий Writer-кандидат, текущий SHA, владельца и состояние `PREPARED`. При любом расхождении — BLOCKED, без автоматического продолжения.
7. **Внутренний долговременный журнал** выполняет одну транзакцию PostgreSQL CAS `PENDING → CONSUMED` (или `DECLINED`). Сначала проверяет всё в транзакции с блокировкой и уникальностью одноразового challenge. Повторный запрос / конфликт / неопределённый ответ дают readback того же challenge, но никогда не создают второй approval. Протокол recovery не освобождает номер REC и не меняет Source.
8. Перед фактическим redemption/finalize обязательно повторно проверить digest, неизменность before-state и принятый code SHA внутри доверенного bounded Writer; предварительный readback и CAS в отдельном сервисе сами по себе не устраняют TOCTOU. Только отдельно принятый доверенный broker может превратить `CONSUMED` с независимыми доказательствами в закрытый подписанный owner-approval receipt. Новый issuer требует независимого security review, точного release SHA, ограничения нового trusted RPC и отдельного решения владельца. **Запрещено выдавать браузерную сессию или технический MATCH за `github.actor_id=308028794`**.
9. Публикация остаётся исключительно существующим bounded Writer с проверками single-writer, независимого verifier, Source bytes, 37 Validation rules, immutable candidate, SQL audit/recovery. Никаких новых полномочий `anon`, `authenticated`, browser, модели или общей роли `service_role` на медицинский DML.

## 2.1. Обнаруженное несовпадение с действующим Writer RPC — BLOCKER

Проверено по принятому `main` SHA:

- `health_writer.propose(p_key,p_changes,p_manifest)` возвращает хеши `candidate_sha`, `before_sha`, `after_sha`, но **не возвращает владельцу до авторизации полный before/after review**.
- `health_writer.review_candidate(p_key)` из `scripts/writer/review_runtime.sql` требует `c.approved = true` и отдельный verifier principal. Этот RPC предназначен для независимой проверки уже авторизованного кандидата.
- **Нельзя** строить браузерный preview на `review_candidate` до согласия или обойти проверку `c.approved`. Такой обход разрушил бы разделение полномочий.

Перед реальным UI необходим **новый узкий preapproval-preview контракт** в приватном серверном контуре: только после владельчески авторизованного `intent`, для его точного `PREPARED` кандидата, с проверенным owner context; доступ строго к этому кандидату, без произвольного `checkpoint()`/SQL и без права удостоверять semantic receipts. Он должен получать полный канонический before/after с серверной подписью/хешем presentation и Source manifest, не перестраивать медицинский смысл автоматически. Прежний verifier RPC сохраняется без ослабления. Изменение является `WRITER_IMPACT` по Issue #62 и требует независимой приёмки точного SHA.

Для синтетического policy-модуля `observed.review_sha` сейчас — **модель будущего доверенного прочтения**, не фактически доступное поле действующего RPC. Пока этой границы нет, реальный `GET /challenges/{id}` и выпуск approval **NO-GO**.

## 3. Контракты (предложение, НЕ активный API)

| Endpoint | Вызывающий | Ограничение |
|---|---|---|
| `POST /internal/challenges` | только защищённый Writer/broker | создать exact challenge после server-side review; без произвольного SQL |
| `GET /challenges/{opaque_id}` | вошедший владелец | прочитать только свой актуальный review; `no-store`, Auth/session/owner check |
| `POST /challenges/{opaque_id}/decision` | браузер владельца | Origin + CSRF + живой session + одноразовый nonce + exact candidate + SQL CAS |
| `GET /challenges/{opaque_id}/status` | владелец или защищённый внутренний исполнитель | read-only, без приватных полей в технических логах |
| `POST /internal/redeem` | только отдельно принятый узкий broker | расходует durable consent для заранее фиксированных Writer RPC; пока НЕ реализован |

API не принимает произвольные таблицы, SQL, URL, путь Sources, роль, медицинскую схему или service-key. Формат ID в URL не является секретом или достаточной авторизацией.

## 4. Требования безопасности

- Auth trust проверяется **сервером на каждый запрос**. `getSession()` / `user_metadata` / переданный клиентом `owner_uid` сами по себе не подходят; проверять `getUser()`/валидированные claims и фактическую сессию. Для медкритичного подтверждения предусмотреть повторный вход или step-up, если аудит потребует; бесплатные ограничения Supabase Session Management не превращать в скрытую зависимость.
- Session, nonce и reviewed SHA связаны с challenge; смена сессии или кандидата инвалидирует подтверждение. Истечение после 5 минут, смена принятых code pins, rollback/recovery, отмена владельцем, выдача нового кандидата — все блокируют старый challenge.
- CSRF и Origin проверяются независимо от CORS, с точным origin allowlist; никаких wildcard, разрешений через query string или тайного approval через GET. Заголовки `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, строгий CSP, `X-Content-Type-Options: nosniff`, защита от clickjacking (`frame-ancestors 'none'`). Не загружать сторонние скрипты.
- Если используются cookie — Secure, HttpOnly, SameSite и token rotation в серверной сессии; если bearer — не сохранять токены в URL/логах и ограничить script bundle/CSP. Выбор конкретного transport ещё не принят.
- Приватное review может содержать медицинские данные: оно остаётся в одобренном приватном хранилище и в защищённой сессии владельца. GitHub получает только opaque идентификаторы и exact digest; никакого Source bytes, REC text или реального owner UID в публичных артефактах.
- `service_role`/secret может быть **только в серверном Edge context**, никогда в browser/client. Привилегированная функция не должна доверять полю запроса `verified=true`; фактическую проверку owner и lock/CAS должен выполнять доверенный сервер.
- Отказ UI не переводит медицинскую операцию в FAILED автоматически без Writer reconciliation. Network UNKNOWN требует перечитать durable status, а не повторно выдавать consent.

## 5. Локальный кандидат

- `scripts/writer/browser_consent_policy.mjs` — чистая синтетическая policy-функция. Принимает исключительно уже проверенные сервером контексты `verified` и `observed`, валидирует one-time challenge и browser answer, вычисляет SHA-256 nonce и выдаёт только `POLICY_MATCH_ONLY`.
- `scripts/writer/test_browser_consent_policy.mjs` — негативные Node.js тесты (synthetic fixture), не требует базу, Auth, GitHub Token, Secrets или сетевые обращения.
- Не реализовано: настоящий Auth verifier, собственно страница, private durable SQL CAS, signer/issuer, Edge Function, Writer RPC adapter, end-to-end signed authorization, browser smoke test, deployment.
- Код не может авторизовать публикацию даже при положительном ответе: `POLICY_MATCH_ONLY` **никогда не является `FINALIZED` и не должен передаваться напрямую как owner receipt**.

## 6. Этапы приёмки

1. **Политика**: независимый аудит модуля/тестов на exact SHA и исправление замечаний; не объявлять тесты достаточными для релиза.
2. **Приватный durable store**: SQL constraints, CAS, isolation, одноразовость, `auth.sessions`, никаких Grants для браузера; негативные конкурентные тесты в disposable PG17 (без production SQL).
3. **Auth + UI**: отдельный защищённый интерфейс на существующей инфраструктуре; origin/CSP/CSRF, негативные чужие сессии и token replay; сквозной browser smoke на синтетике.
4. **Signed broker**: независимое криптографическое issuer-тестирование, уязвимость `github.actor_id` не обходить; отдельное принятие изменений в trusted broker, Writer contract/RPC, полный exact SHA release gate.
5. **E2E**: два отдельных владельческих решения `intent`/`candidate`, независимый verifier, Source readback, конкурентный Writer, UNKNOWN/recovery, 37 rule applicability, отказ от direct clinical DML.
6. **Owner GO**: immutable BASE_SHA/HEAD_SHA/diff, независимый review, ручной GO, повторный readback, изменения main только после reaccept runtime + broker. Отдельная медицинская/эксплуатационная авторизация остаётся обязательной.

## 7. Открытые вопросы для архитектурного координатора (не блокируют локальную разработку)

- Где именно размещать страницу: отдельная Edge Function в том же Supabase проекте либо изолированная route существующего Pages-хостинга? Предпочтение — **Edge Function**, чтобы не расширять read-only PWA и не открывать медицинский payload через Pages. Конкретный hosting/login/CSP должен быть проверен без production изменений.
- Какой серверный signing principal и защищённый RPC будет единственным издателем согласия после независимой security приёмки? До решения использовать Browser consent только как дополнительное evidence, а не замену signed GitHub Owner workflow.
- Достаточна ли текущая Auth-сессия или нужен step-up перед публикацией? Решение зависит от независимой оценки threat model; пока проектировать возможность server-enforced fresh login.

**NO-GO:** до выполнения этих условий новый ChatGPT Gateway остаётся read-only для медицинских операций; действующий принятый Writer не отключается и не переопределяется.


## 8. Проверка CI и зависимости текущих веток — 14.10.2026

- Read-only GitHub сверка: `main` и `writer-code` имеют BASE_SHA `3409791f1ffc5749020e7ff07139b0cec722f6fc`; target feature branch создана на том же SHA.
- Три новых пути данного предложения отсутствуют в текущем принятом `main`, конфликт имени не найден.
- Draft #84 содержит иной кандидат контракта Gateway, включая правку `.github/workflows/code-validation.yml`. Он **не принят** в `writer-code`. Нельзя полагаться на его self-controlled CI как на релизное доказательство.
- На принятом `main` workflow `code-validation.yml` не запускает новую `test_browser_consent_policy.mjs` автоматически для PR в `writer-code`. До независимой приёмки требуется либо отдельно согласованная проверяемая CI-правка, либо явно приложенный signed/exact-SHA тестовый протокол; успешный локальный `node --test` не равен GitHub protected required check.
- Read-only Supabase сверка показывает единственную действующую Edge Function `health-writer-authorization-v1`; нового browser-consent endpoint нет. Существующую функцию, её secrets и signed owner authorization нельзя менять без отдельного contract/release gate.
- Перед написанием `preapproval-preview` RPC нужна матрица `p_key -> approved intent -> PREPARED -> private candidate projection -> exact presentation digest` с проверкой ownership, expiry и отсутствия ослабления отдельного `review_candidate()` для verifier. Нельзя считать `observed.review_sha` фактически полученным от Writer до принятия этой функции.
- Проверяемый scope этого кандидата: исключительно документация, синтетическая policy и тесты. Нет изменённой production SQL-схемы, браузерного приложения, Edge, Auth, Secrets, Source или медицинских строк.

**Ограничение проверки:** синтетические тесты не подтверждают криптографическую идентичность владельца, живость Supabase сессии, источник `verified`/`observed`, SQL CAS, реальное поведение Edge или медицинскую публикацию. Эти вопросы остаются gate blockers.
