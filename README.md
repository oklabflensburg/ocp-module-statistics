# ocp-module-statistics

Installable Statistics query and municipal import module for Open City Planner.

Version 0.3.0 keeps the public SDK `StatisticsQueryPort` as `statistics.query@1`
and adds the `statistics.import` module job. The job uses the Host-controlled HTTP,
settings, database, scheduler, and observability ports; it publishes no Statistics
API or UI.

## Import configuration

The Host module settings registry loads only the `statistics` namespace. Enabling
the module without the required provider origin fails at startup.

| Environment key | Required/default | Meaning |
| --- | --- | --- |
| `OCP_MODULE_STATISTICS_PROVIDER_BASE_URL` | required | HTTP(S) Superset origin without credentials, query, or fragment |
| `OCP_MODULE_STATISTICS_PROVIDER_DASHBOARD_ID` | Flensburg Zahlenspiegel UUID | Expected dashboard |
| `OCP_MODULE_STATISTICS_PROVIDER_TIMEOUT_SECONDS` | `30` | Per-request upper bound, 1–300 seconds |
| `OCP_MODULE_STATISTICS_IMPORT_ENABLED` | `true` | Whether the module contributes its import job |
| `OCP_MODULE_STATISTICS_IMPORT_RETRY_COUNT` | `2` | Retries for timeouts, connection failures, and HTTP 5xx only |
| `OCP_MODULE_STATISTICS_IMPORT_DATASET` | `flensburg-superset-v1` | Reviewed provider mapping version |
| `OCP_MODULE_STATISTICS_IMPORT_SCHEDULE_SECONDS` | unset | Optional interval; unset keeps the job manually triggerable |

Configuration errors, unsupported datasets, schema/value errors, and mapping
errors are not retried. The Host HTTP client additionally owns connect/read
timeouts, connection limits, redirects, proxy isolation, and its User-Agent.

## Ownership

The module adopts ownership of these existing, unqualified tables without creating,
copying, or dropping data:

- `statistical_datasets`
- `statistical_metrics`
- `external_area_mappings`
- `statistical_observations`
- `statistical_import_runs`

The import writes only these five tables. The historical Host revisions
`20260816_0016` and `20260901_0035` remain immutable in the Host lineage; version
0.3.0 declares no migration source.

Analysis Areas owns hierarchy resolution and passes a complete
`StatisticsSelection`; Statistics contains no quarter-parent rule.

## Import lifecycle and operations

The provider response is checked for the reviewed dashboard, exact dataset/chart
inventory, CSV media type and schema. Rows are then validated completely before a
write starts: periods, numeric values, dimensions, duplicates, the 13 district
names, coverage, metrics, and stored mappings must all be unambiguous. The canonical
observations are upserted by the existing business key
`(metric_id, statistical_area_id, period_start, source_area_id)`; stable row hashes
make identical runs no-ops and changed values updates.

An audit row is committed as `RUNNING` before provider access. Dataset, metric,
mapping and observation changes plus the final `SUCCESS` update share one
transaction. A failure rolls that transaction back and records a bounded summary as
`FAILED`; provider payloads and secrets are never stored. Logs, traces and metrics
cover start, retry, success/failure, duration, row counts and failure class.

Disabling the module removes all of its runtime contributions. Setting
`IMPORT_ENABLED=false` keeps queries available but contributes no import job. If a
schedule is configured, the generic job registry owns it; there is no Host-specific
scheduler. Roll back by disabling 0.3.0 or deploying the previous immutable module
release. Imported valid data is retained and no automatic database downgrade runs.

## Development

```bash
cd backend
uv sync --frozen --extra dev
uv run ruff check src tests
uv run pytest
uv build --wheel --clear

cd ../frontend
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test
pnpm build

cd ..
OCP_HOST_CHECKOUT=/path/to/open-city-planner scripts/build-bundle
sha256sum -c dist/statistics-0.3.0.ocp.sha256
OCP_HOST_CHECKOUT=/path/to/open-city-planner scripts/host-contract-test
```
