# ocp-module-statistics

Installable read-only Statistics module for Open City Planner.

Version 0.2.0 provides the existing public SDK `StatisticsQueryPort` as
`statistics.query@1`. It reads the retained municipal statistics tables and does
not publish a Statistics API or UI.

## Ownership

The module adopts read ownership of these existing, unqualified tables without
creating, copying, or dropping data:

- `statistical_datasets`
- `statistical_metrics`
- `external_area_mappings`
- `statistical_observations`
- `statistical_import_runs`

The first historical migration also seeded Host cache state, so published Alembic
revisions remain in the Host lineage for now. The module declares no migration source.

Analysis Areas owns hierarchy resolution and passes a complete
`StatisticsSelection`; Statistics contains no quarter-parent rule.

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
sha256sum -c dist/statistics-0.2.0.ocp.sha256
OCP_HOST_CHECKOUT=/path/to/open-city-planner scripts/host-contract-test
```
