# Statistics import runbook

Configure the `statistics` module namespace as listed in the root README, enable the
module, and trigger `statistics.import` through the Host's generic job runner. Leave
the schedule unset until the provider contract and mapping have been reviewed in the
target environment.

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
