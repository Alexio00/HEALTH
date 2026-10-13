# HEALTH-TEST consent UI: release and threat review

This page supports only the isolated OAuth/synthetic-queue acceptance probe.
It cannot prepare, confirm or finalize a clinical Writer operation.

Runtime values are not committed: a fixed trusted TEST HTTPS endpoint returns
only a modern publishable API key, registered public client ID and exact
ChatGPT callback. These three values are intentionally public browser parameters,
not server credentials. Their source row remains in private TEST configuration.
The page rejects extra fields, legacy JWT keys, malformed client IDs and other
callback origins/paths. It never accepts an Auth/API root from that response.

The separate server route uses an explicit three-field projection. It cannot
return owner UUID, service credentials, policy or queue data. Missing server
credentials/configuration fails closed. Its availability does not enable MCP
authorization; the independently disabled private policy still gates tool calls.
CORS permits the existing Pages origin; CORS is not authentication.

The login form stays disabled without a valid authorization ID and validated
configuration. The password goes only to fixed HEALTH-TEST Auth over HTTPS,
is cleared after the response or error, and is never logged or stored. Access
tokens stay in page memory. Auth details are read again before consent;
exact client/callback and only openid must still match. An unrecognized response
or already-granted redirect-only response fails closed rather than auto-approving.
Consent for this test does not constitute approval of any clinical write.

The existing CSP allows only local scripts/styles and fixed TEST network origin;
no third-party scripts are added. OAuth pages/query URLs are excluded from the
PWA worker's offline cache. This PR does not edit the worker or release workflows.
The Pages origin and its reviewed static source remain trusted login UI; changes
to them must retain protected PR/CI/release review. No password/token is a fixture.

Tests exercise malformed/extra configuration, callback/scope rejection, network
failure, invalid authorization IDs and the disabled login gate. They do not prove
real password login, owner OAuth, S256-only enforcement or clinical correctness.
Real OAuth/negative-flow evidence and an independent production security audit
remain required. A public Pages release does not change HEALTH/main acceptance.

## Восстановление пароля HEALTH-TEST через email

На странице подключения есть ссылка «Не помню пароль». Отдельный режим
`consent.html?mode=recovery` работает без OAuth authorization_id. Запрос
отправляется только в фиксированный HEALTH-TEST Auth `/recover`, с точным
адресом этой страницы и PKCE/S256. Стандартное письмо Supabase содержит
ссылку восстановления. Custom SMTP, изменение шаблона или Pro не требуются.
Встроенный почтовый сервис ограничен разрешёнными адресами команды и своей
квотой; ответ API не доказывает доставку письма в почтовый ящик.

Открой ссылку в том же браузере в течение 15 минут. В localStorage хранится
только случайный PKCE verifier и время запроса, в отдельном TEST-ключе.
Email, пароль, access/refresh token туда не записываются. Запись отклоняется
после 15 минут и удаляется при следующем обращении; код возврата потребляет
verifier перед единственной попыткой обмена. Закрытие исходной вкладки не
удаляет verifier, чтобы письмо можно было открыть в новой вкладке этого
браузера. Другой профиль/браузер, повтор и потеря verifier требуют нового
запроса. Повторный запрос блокируется, пока действителен предыдущий verifier.

Страница принимает только точный origin/path, режим recovery и один UUIDv4
кода Supabase PKCE. Неизвестные параметры, дубликаты, OAuth authorization_id,
внешние адреса и implicit-token fragment отклоняются. Код/ошибочные параметры
удаляются из адреса до сетевых запросов. Referrer отключён; запросы без cookies,
кэша и переходов по redirect, с ограниченным timeout. Серверный flow state
Supabase связывает код с recovery/S256 и потребляет его при успешном обмене.
Это проверено по официальному Auth source, не является доказательством всех
отрицательных сценариев текущей hosted-версии.

Полученная recovery-сессия остаётся только в памяти, не обновляется автоматически
и используется максимум 10 минут или до её server expiry. Новый пароль должен
содержать 12–128 символов; пользователь вводит его дважды. Изменение идёт через
Auth `PUT /user`, с проверкой UUID ответа против UUID recovery-сессии. Затем
`POST /logout?scope=global` завершает refresh-сессии. Уже выданные access JWT
могут оставаться валидными до своего expiry. Если logout не подтверждён,
интерфейс сообщает это отдельно от успешной смены пароля. При неоднозначном
ответе смена не повторяется автоматически. Поля пароля очищаются, токен
удаляется из памяти после попытки/ухода со страницы, BFCache не восстанавливает
recovery-сессию. Существующая OAuth-политика и медицинский Writer не меняются.

Используй восстановление из этой страницы, не кнопку админского Dashboard:
эта реализация намеренно не принимает implicit access tokens от старых писем.
Почтовый сканер всё ещё может погасить стандартную ссылку; автоматическое
потребление писем нашим интерфейсом не выполняется. При проблеме запроси новое
письмо после истечения предыдущей попытки.

Синтетические тесты проверяют S256, route/schema/TTL, неверный/повторный код,
ошибки конфигурации/хранилища/сети, истечение сессии, совпадение паролей,
UUID readback, очистку полей, logout и отсутствие OAuth consent. Доставка
реального письма и реальная смена пароля требуют самостоятельного действия
пользователя; синтетический PASS не считается таким доказательством.

## Подготовленный scope-контракт ChatGPT

Кандидат принимает ровно `openid email offline_access`, в любом порядке, без
дубликатов и дополнительных scopes. `openid` подтверждает TEST-учётку;
`email` разрешает приложению видеть её email; `offline_access` допускает refresh
в пределах 30-минутного TEST-окна. Набор проверяется повторно непосредственно
перед согласием. Это не разрешение медицинских действий.

Активация зависит от согласия владельца, согласованного Edge/Auth-hook/SQL
кандидата и приватной policy со сроком. Сам frontend не включает серверные
права, не выставляет срок и не заменяет GitHub OIDC. До согласованного выпуска
кандидата прежняя опубликованная страница продолжает отклонять scopes шире
openid. Реальная выдача OAuth/refresh и совместимость UserInfo пока NOT_VERIFIED.

