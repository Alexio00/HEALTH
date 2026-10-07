# Security

## Public repository

Never commit:
- real medical records
- laboratory values
- source files
- private filenames containing sensitive information
- private storage URLs or object IDs
- production account identifiers
- OAuth tokens
- service-role/secret keys
- database passwords
- backup credentials
- real `.env` files

## Browser

The PWA is read-only.

Allowed:
- public/publishable Supabase client key
- non-sensitive runtime configuration

Forbidden:
- service-role key
- database password
- storage credentials
- AI write credentials

## Database

- public signup disabled
- one administrative user initially
- anonymous users receive no medical data
- authenticated browser access is SELECT-only
- Row Level Security is mandatory on user-facing medical tables

## AI write path

AI clients call controlled server operations. They do not receive raw service-role or unrestricted SQL access.

## Source storage

Source files remain private. Browser source opening relies on the owner's authenticated provider session rather than public source URLs.

## Logging

Do not log medical payloads, raw source contents or secrets into public CI logs.
