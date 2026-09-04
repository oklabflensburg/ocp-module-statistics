# Statistics import runbook

Import is opt-in. Enabling Statistics with no import settings is a supported
query-only deployment: `statistics.query@1` is registered and no import job exists.
Reads remain available independently of provider configuration.

To import, configure the `statistics` module namespace as listed in the root README,
set `OCP_MODULE_STATISTICS_IMPORT_ENABLED=true`, provide
`OCP_MODULE_STATISTICS_PROVIDER_BASE_URL`, restart the Host, and trigger
`statistics.import` through the generic job runner. Enabling import without a valid
provider URL fails during settings validation. Leave the schedule unset until the
provider contract and mapping have been reviewed in the target environment.

A healthy run progresses from `RUNNING` to `SUCCESS` in
`statistical_import_runs`. Operators can compare `rows_downloaded`, `rows_imported`,
`rows_updated`, `rows_unchanged`, checksum, schema hash, and duration. `FAILED`
records contain a short failure class/summary. Repeated unchanged runs should report
zero inserts and updates.

Mapping or schema failures require review; do not increase retries. Timeout,
connection, or 5xx failures may be retried within the configured bound. To stop
imports while retaining reads, set `IMPORT_ENABLED=false` and restart the Host so
the job is absent. For full rollback, disable this release or deploy the previous
immutable release. Do not delete imported rows or downgrade the historical Host
migrations.
