# Statistics module architecture

## Public boundary

```text
Analysis Areas
    → Service Registry (`statistics.query@1`)
    → StatisticsQueryPort
    → SqlStatisticsQueryService
    → retained statistical_* tables
```

The public DTOs and `StatisticsQueryPort` remain Host SDK contracts. The module
registers their implementation through the generic service registry. It imports no
Host internals and opens no database sessions; callers own sessions and transactions.

## Persistence decision

The module declares the five existing statistics tables as `adopted_tables` and
ships no migrations in 0.2.0. Host revision `20260816_0016` originally created all
five tables but also touched generic `cache_versions`. Revision `20260901_0035`
decoupled statistics areas from Analysis Areas and is statistics-only. Both published
revisions stay immutable in the Host migration history until migration ownership can
be separated without adopting mixed-domain behavior.

No schema change, table recreation, data copy, or destructive migration is part of
this release.
