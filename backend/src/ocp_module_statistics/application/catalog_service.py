"""Read projections for Statistics-owned public and operator surfaces."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ocp_module_statistics.api.schemas import (
    StatisticsImportRunDto,
    StatisticsImportRunPageDto,
    StatisticsMetricDto,
    StatisticsMetricPageDto,
    StatisticsSourceDto,
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _import_run(row: object) -> StatisticsImportRunDto:
    return StatisticsImportRunDto(
        id=int(row["id"]),  # type: ignore[index]
        source=str(row["source"]),  # type: ignore[index]
        started_at=row["started_at"],  # type: ignore[index]
        finished_at=row["finished_at"],  # type: ignore[index]
        status=str(row["status"]),  # type: ignore[index]
        rows_downloaded=int(row["rows_downloaded"]),  # type: ignore[index]
        rows_imported=int(row["rows_imported"]),  # type: ignore[index]
        rows_updated=int(row["rows_updated"]),  # type: ignore[index]
        rows_unchanged=int(row["rows_unchanged"]),  # type: ignore[index]
        rows_rejected=int(row["rows_rejected"]),  # type: ignore[index]
        error_summary=(str(row["error_message"])[:500] if row["error_message"] else None),  # type: ignore[index]
    )


class StatisticsCatalogService:
    async def sources(self, session: AsyncSession, *, limit: int) -> list[StatisticsSourceDto]:
        rows = (
            (
                await session.execute(
                    text("""
                    SELECT source,external_dataset_id,name,description,source_url,license,
                           update_frequency,last_import_at,source_updated_at
                    FROM statistical_datasets
                    ORDER BY name,external_dataset_id
                    LIMIT :limit
                    """),
                    {"limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return [
            StatisticsSourceDto(
                source=str(row["source"]),
                dataset=str(row["external_dataset_id"]),
                name=str(row["name"]),
                description=str(row["description"]) if row["description"] else None,
                source_url=str(row["source_url"]),
                license=str(row["license"]),
                update_frequency=str(row["update_frequency"]),
                last_import_at=row["last_import_at"],
                source_updated_at=row["source_updated_at"],
            )
            for row in rows
        ]

    async def metrics(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        category: str | None,
        source: str | None,
        offset: int,
        limit: int,
    ) -> StatisticsMetricPageDto:
        conditions = ["metric.public=true"]
        parameters: dict[str, object] = {"offset": offset, "limit": limit}
        if query:
            conditions.append(
                "(lower(metric.name) LIKE :query ESCAPE '\\' "
                "OR lower(metric.key) LIKE :query ESCAPE '\\' "
                "OR lower(coalesce(metric.description,'')) LIKE :query ESCAPE '\\')"
            )
            parameters["query"] = f"%{_escape_like(query.casefold())}%"
        if category:
            conditions.append("lower(metric.category)=:category")
            parameters["category"] = category.casefold()
        if source:
            conditions.append("lower(dataset.source)=:source")
            parameters["source"] = source.casefold()
        where = " AND ".join(conditions)
        total = await session.scalar(
            text(f"""
                SELECT count(*)
                FROM statistical_metrics metric
                JOIN statistical_datasets dataset ON dataset.id=metric.dataset_id
                WHERE {where}
            """),
            parameters,
        )
        rows = (
            (
                await session.execute(
                    text(f"""
                    SELECT metric.key,metric.name,metric.description,metric.category,
                           metric.unit,metric.value_type,metric.aggregation_method,
                           metric.public,dataset.source,
                           dataset.external_dataset_id AS dataset,dataset.name AS dataset_name
                    FROM statistical_metrics metric
                    JOIN statistical_datasets dataset ON dataset.id=metric.dataset_id
                    WHERE {where}
                    ORDER BY metric.category,metric.name,metric.key
                    OFFSET :offset LIMIT :limit
                    """),
                    parameters,
                )
            )
            .mappings()
            .all()
        )
        return StatisticsMetricPageDto(
            items=[StatisticsMetricDto.model_validate(dict(row)) for row in rows],
            total=int(total or 0),
            offset=offset,
            limit=limit,
        )

    async def import_runs(
        self, session: AsyncSession, *, offset: int, limit: int
    ) -> StatisticsImportRunPageDto:
        total = await session.scalar(
            text("SELECT count(*) FROM statistical_import_runs")
        )
        rows = (
            (
                await session.execute(
                    text("""
                    SELECT id,source,started_at,finished_at,status,rows_downloaded,
                           rows_imported,rows_updated,rows_unchanged,rows_rejected,
                           error_message
                    FROM statistical_import_runs
                    ORDER BY started_at DESC,id DESC
                    OFFSET :offset LIMIT :limit
                    """),
                    {"offset": offset, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return StatisticsImportRunPageDto(
            items=[_import_run(row) for row in rows],
            total=int(total or 0),
            offset=offset,
            limit=limit,
        )

    async def last_import_run(self, session: AsyncSession) -> StatisticsImportRunDto | None:
        row = (
            (
                await session.execute(
                    text("""
                    SELECT id,source,started_at,finished_at,status,rows_downloaded,
                           rows_imported,rows_updated,rows_unchanged,rows_rejected,
                           error_message
                    FROM statistical_import_runs
                    ORDER BY started_at DESC,id DESC
                    LIMIT 1
                    """)
                )
            )
            .mappings()
            .first()
        )
        return _import_run(row) if row is not None else None
