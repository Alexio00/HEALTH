# Frontend

The HEALTH frontend is a static read-only PWA deployed through GitHub Pages.

## Security model

- Supabase publishable key only; no secret/service-role key.
- No sign-up UI.
- Login uses Supabase Auth email/password.
- A signed-in user must also exist in public.app_readers.
- Browser access is SELECT-only and enforced again by PostgreSQL grants + RLS.
- Service worker caches only same-origin application-shell files.
- Supabase/Google Drive/API responses are never cached by the service worker.
- No medical data is committed to this public repository.

## Routes

- #/ — current state
- #/records — record index
- #/records/<record_id> — REC
- #/sources/<source_id> — source metadata and authenticated Drive locator

## Runtime

The browser uses @supabase/supabase-js 2.117.2 from a version-pinned CDN URL.
