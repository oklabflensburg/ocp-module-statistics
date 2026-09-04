# OCP Statistics backend

Python wheel for the standalone Open City Planner Statistics query/import module.

Version 0.3.0 registers `statistics.query@1` and the optional
`statistics.import` job. Import is opt-in and disabled by default, so query-only
deployments need no provider URL. Setting `IMPORT_ENABLED=true` requires a valid
provider URL during settings validation. See the repository README and architecture
document for the settings, validation, retry, transaction, and rollback contracts.
Project documentation and provenance are maintained in the repository root.
