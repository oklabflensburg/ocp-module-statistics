# Statistics public surfaces audit

Stand: 2026-09-04 · [open-city-planner#221](https://github.com/oklabflensburg/open-city-planner/issues/221)

## Decision

Statistics owns the public source and metric catalog and the permission-protected
operational view of its own imports. Area selection, area summaries, time series,
comparisons, and their visualisations remain in Analysis Areas. Geometry and
market aggregates over polygons remain in Polygons.

The audit covered the current Host, the pre-slim-host tree before `de023dd`, and
the extraction inventory on `staging/epic-91-modular-host`. Prometheus metrics,
performance measurements, and editorial uses of “comparison” are not Statistics
product surfaces.

| Historical surface | Previous purpose | Classification | Current owner | Still needed? | Replacement |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v1/analytics/fast-facts` | Manually maintained global vacancy, chain-store, centrality, and purchasing-power values | `OBSOLETE` | None; the retained `city_metrics` table has no active runtime | No confirmed product contract | None; do not restore from the inactive table |
| `GET /api/v1/analytics/fast-facts/verwaltung` and `PATCH /api/v1/analytics/fast-facts` | Read and edit the global fast facts | `OBSOLETE` | None | No confirmed product contract | None; `/verwaltung/kennzahlen` is not restored |
| `GET /api/v1/analytics/overview` and `/benchmarks` | Filtered aggregates over Host polygons | `OWNED_BY_POLYGONS` | Polygons | Yes, only in their current polygon/area contexts | Existing Polygon contracts and Analysis Areas orchestration |
| `POST /api/v1/analytics/compare` and `/vergleich` | Compare selected areas using polygon aggregates | `OWNED_BY_ANALYSIS_AREAS` | Analysis Areas, consuming public Polygon ports | Yes, but not as a Statistics surface | Existing area comparison contract/UI |
| Area detail statistics and charts | Summary and time series for a selected area | `OWNED_BY_ANALYSIS_AREAS` | Analysis Areas, consuming `statistics.query@1` | Yes; regression gate | `/api/v1/analysis-areas/by-slug/{slug}/statistics` and `.../statistics/{metric_key}` |
| Historical Statistics import CLI | Run the Zahlenspiegel import directly | `REPLACE` | Statistics plus the generic Host job runner | Yes for operators | Registered `statistics.import` job; no direct HTTP-to-service call |
| Historical import status and run records | Diagnose provider imports | `ADMIN_ONLY` | Statistics | Yes | Protected `/api/v1/statistics/import-status` and `/api/v1/statistics/import-runs` |
| Historical source metadata embedded in area responses | Explain provenance and data currency | `KEEP` | Statistics | Yes | Public `/api/v1/statistics/sources`; area responses stay unchanged |
| Historical metric definitions embedded in area responses | Identify published municipal measures | `KEEP` | Statistics | Yes | Public, filterable `/api/v1/statistics/metrics`; area responses stay unchanged |
| Polygon detail metrics (`/polygons/{id}/metrics`) | Geometry values for a user polygon | `OWNED_BY_POLYGONS` | Polygons | Yes | Existing Polygon API/UI |

## Implemented contract

Public:

- `GET /api/v1/statistics/sources`
- `GET /api/v1/statistics/metrics` with `query`, `category`, `source`, `offset`, and
  bounded `limit`

Operator-only (`statistics.import`):

- `GET /api/v1/statistics/import-status`
- `GET /api/v1/statistics/import-runs` with bounded pagination

The module deliberately does not provide a manual import endpoint. The current
public SDK lets a module register a job but exposes no generic job-execution port to
module HTTP handlers. Calling `StatisticsImportService` directly would bypass the
authoritative runner lifecycle, timeout, retry, and observability contract. A POST
can be added later when the Host offers a generic, public trigger port.

## Frontend ownership

The module contributes `/statistik`, `/statistik/datenquellen`,
`/statistik/kennzahlen`, and the permission-aware
`/statistik/importstatus`. The public primary navigation points to the overview;
the import-status link is an admin navigation contribution visible only with
`statistics.import`.

The current manifest contracts already provide stable module ID, name, version,
route sources, navigation grouping, labels, and priorities. They do not yet define
generic presentation fields for icon, category, or long description. Those fields
are therefore not invented as Statistics-specific manifest extensions; #225 can
add them once to the generic schema and consume the existing declarative routes.

No global dashboard, area detail, area comparison, polygon aggregate, legacy
`/vergleich`, or `/verwaltung/kennzahlen` page is restored.
