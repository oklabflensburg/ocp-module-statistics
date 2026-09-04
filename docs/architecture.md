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

The independent write path is:

```text
statistics settings → statistics.import job → Host HTTP port → Superset DTO
  → complete validation/mapping → one database transaction → five owned tables
```

The import service opens sessions only through `ModuleContext.database`. Provider
code sees only the public HTTP protocols. No Analysis Areas or Polygon ORM is
imported, and no Host cache/audit table is touched.

## Persistence decision

The module declares the five existing statistics tables as `adopted_tables` and
ships no migrations in 0.3.0. Host revision `20260816_0016` originally created all
five tables but also touched generic `cache_versions`. Revision `20260901_0035`
decoupled statistics areas from Analysis Areas and is statistics-only. Both published
revisions stay immutable in the Host migration history until migration ownership can
be separated without adopting mixed-domain behavior.

No schema change, table recreation, data copy, or destructive migration is part of
this release.

## Historical characterization

Retained from the removed Host implementation are the public Zahlenspiegel
dashboard identity, exact five-dataset/27-chart inventory, strict CSV schemas, the
reviewed Flensburg municipality plus 13 district mapping, canonical metrics,
suppression handling, annual aggregation, checksums, row hashes, idempotent upserts,
and success/failure import-run audit.

Discarded are direct `httpx` construction, global Host environment settings,
Analysis Areas ORM lookup/foreign keys, Host statistics models and CLI, cache-version
bumps, and writes to the Host admin audit log. The current
`external_area_mappings` table is the complete Statistics-owned identity boundary.

## Failure and security boundaries

All provider rows are validated before catalog or observation writes. A late error
therefore cannot create partial observations. Provider retries are limited to
timeouts, connection failures, and 5xx responses; contract, mapping, configuration,
and 4xx errors fail immediately. The Host transport bounds connections and network
behavior, while the module adds a per-request and total job timeout.

Audit summaries contain only exception class and bounded module-generated messages;
raw payloads, response bodies, credentials, and provider URLs from configuration are
not logged. SQL parameters carry every provider-derived value.
