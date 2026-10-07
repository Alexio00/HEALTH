# Architecture

## Goal

HEALTH separates application code, structured health data, original source files, backups, and scheduled automation.

## Components

1. **Public code repository**
   - schema and migrations
   - Health API contracts/implementation
   - read-only PWA
   - tests and deployment logic
   - synthetic fixtures only

2. **PostgreSQL**
   - canonical structured data
   - operation state and validation evidence
   - provider-neutral source metadata
   - no dependency on Google Drive paths as canonical identifiers

3. **Private source storage**
   - original medical source files
   - addressed through logical source IDs plus physical location rows

4. **Read-only PWA**
   - authenticated user only
   - reads current PostgreSQL data
   - never writes medical data
   - deep links use stable health IDs, not provider object IDs

5. **Health API**
   - controlled server-side domain operations for AI clients
   - owns transaction/validation logic
   - AI clients never receive unrestricted database credentials

6. **Independent scheduler**
   - private automation repository/service
   - database backups
   - source backups
   - backup verification
   - optional keep-alive and dispatch of public-repo workflows

## Trust boundaries

- Browser: publishable/client credentials only.
- Health API runtime: secrets stay server-side.
- Public GitHub: no medical data, no private provider locators, no production credentials.
- Source provider identifiers are operational locators, never medical identifiers.

## Portability

- Database must be restorable into standard PostgreSQL from a portable dump.
- Source identity survives a storage-provider move.
- PWA can move to another static host.
- Health API must remain callable by multiple AI clients.
- Provider-specific logic must be isolated from domain data.

## Current source-of-truth boundary

The existing health database remains authoritative until an explicit cutover. MVP migration is copy-first and must not delete or rewrite the source system.
