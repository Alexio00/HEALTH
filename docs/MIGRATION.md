# Migration

## Strategy

Migration is copy-first, never move-first.

The current health database remains canonical until explicit cutover approval.

## MVP subset

Choose the minimum representative set that covers:
- ordinary REC
- REC with source
- REC with Labs
- REC linked to a Case
- REC touching Plan, Question or Monitoring when practical
- several randomly selected REC to reduce cherry-picking bias

## MVP flow

1. Freeze the selected source snapshot logically.
2. Export only the required structured rows.
3. Copy only required source files to target primary source storage.
4. Create logical `sources` and physical `source_locations`.
5. Preserve existing medical IDs.
6. Import records and related entities.
7. Render REC from PostgreSQL, not legacy Docs/Markdown.
8. Compare old -> new for content, links and provenance.
9. Validate source opening from the PWA.
10. Test backup and restore on the MVP database.
11. Produce an acceptance report.

## Prohibited during MVP

- deleting source-system data
- changing the canonical source
- full migration
- production cutover
- rewriting unsupported medical facts
- normalizing literal laboratory values or ranges
