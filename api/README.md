# API

Server-side Health API implementation lives here.

The browser must never call write operations directly. AI clients receive domain operations, not unrestricted database credentials.

Initial implementation choice is intentionally deferred until the live Supabase project is connected and the Edge Functions / PostgreSQL RPC trade-off is tested against the MVP.
