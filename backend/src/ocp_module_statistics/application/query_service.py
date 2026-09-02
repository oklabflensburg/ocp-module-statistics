"""Read-only projection of retained municipal statistics tables."""

from collections.abc import Mapping

from app.platform.modules.sdk import (
    AreaStatistics,
    AreaStatisticSeries,
    StatisticsArea,
    StatisticSeriesPoint,
    StatisticsSelection,
    StatisticsSource,
    StatisticValue,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _statistics_area(value: StatisticsArea) -> StatisticsArea:
    return StatisticsArea(
        id=value.id,
        slug=value.slug,
        name=value.name,
        area_type=value.area_type,
    )


async def _statistics_mapping(
    session: AsyncSession, selection: StatisticsSelection
) -> Mapping[str, object] | None:
    return (
        await session.execute(
            text("""
              SELECT target.id AS target_id,
                     municipality.id AS municipality_id,
                     target.source AS source
              FROM external_area_mappings target
              JOIN external_area_mappings municipality
                ON municipality.source=target.source
              WHERE target.external_area_name=:target_name
                AND target.level=:target_level
                AND municipality.external_area_name=:municipality_name
                AND municipality.level=:municipality_level
              ORDER BY target.source
              LIMIT 1
            """),
            {
                "target_name": selection.target.name,
                "target_level": selection.target.area_type,
                "municipality_name": selection.municipality.name,
                "municipality_level": selection.municipality.area_type,
            },
        )
    ).mappings().first()


async def _statistics_source(
    session: AsyncSession, source: str
) -> StatisticsSource | None:
    row = (
        await session.execute(
            text("""
              SELECT name,source_url,license,last_import_at,source_updated_at
              FROM statistical_datasets
              WHERE source=:source AND last_import_at IS NOT NULL
              ORDER BY last_import_at DESC,id DESC
              LIMIT 1
            """),
            {"source": source},
        )
    ).mappings().first()
    if row is None:
        return None
    return StatisticsSource(
        name=str(row["name"]),
        url=str(row["source_url"]),
        license=str(row["license"]),
        source_updated_at=row["source_updated_at"],
        last_import_at=row["last_import_at"],
    )


class SqlStatisticsQueryService:
    """Implement the public SDK port without owning the caller's transaction."""

    async def for_selection(
        self, session: AsyncSession, selection: StatisticsSelection
    ) -> AreaStatistics | None:
        mapping = await _statistics_mapping(session, selection)
        if mapping is None:
            return None
        rows = (
            await session.execute(
                text("""
                  WITH ranked AS (
                    SELECT observation.*,row_number() OVER (
                      PARTITION BY observation.metric_id
                      ORDER BY observation.period_start DESC
                    ) AS rank
                    FROM statistical_observations observation
                    WHERE observation.statistical_area_id=:target_id
                  )
                  SELECT metric.key,metric.name,metric.category,metric.unit,
                         ranked.value_numeric,ranked.period_start,ranked.is_calculated,
                         municipality.value_numeric AS municipality_value
                  FROM ranked
                  JOIN statistical_metrics metric ON metric.id=ranked.metric_id
                  JOIN statistical_datasets dataset ON dataset.id=metric.dataset_id
                  LEFT JOIN statistical_observations municipality
                    ON municipality.metric_id=ranked.metric_id
                   AND municipality.statistical_area_id=:municipality_id
                   AND municipality.period_start=ranked.period_start
                  WHERE ranked.rank=1 AND metric.public=true AND dataset.source=:source
                  ORDER BY metric.category,metric.name
                """),
                mapping,
            )
        ).mappings().all()
        latest = []
        for row in rows:
            value = row["value_numeric"]
            municipality_value = row["municipality_value"]
            difference = (
                value - municipality_value
                if value is not None and municipality_value is not None
                else None
            )
            relative_difference = (
                difference / municipality_value * 100
                if difference is not None and municipality_value
                else None
            )
            latest.append(
                StatisticValue(
                    key=str(row["key"]),
                    name=str(row["name"]),
                    category=str(row["category"]),
                    value=value,
                    unit=str(row["unit"]),
                    period=str(row["period_start"].year),
                    period_start=row["period_start"],
                    area_level=selection.target.area_type,
                    is_calculated=bool(row["is_calculated"]),
                    municipality_value=municipality_value,
                    difference=difference,
                    relative_difference=relative_difference,
                )
            )
        return AreaStatistics(
            area=_statistics_area(selection.requested),
            statistics_area=_statistics_area(selection.target),
            inherited_from_parent=selection.inherited,
            source=await _statistics_source(session, str(mapping["source"])),
            latest=tuple(latest),
        )

    async def series_for_selection(
        self,
        session: AsyncSession,
        selection: StatisticsSelection,
        metric_key: str,
    ) -> AreaStatisticSeries | None:
        mapping = await _statistics_mapping(session, selection)
        if mapping is None:
            return None
        metric = (
            await session.execute(
                text("""
                  SELECT metric.id,metric.key,metric.name,metric.unit,metric.category
                  FROM statistical_metrics metric
                  JOIN statistical_datasets dataset ON dataset.id=metric.dataset_id
                  WHERE metric.key=:metric_key AND metric.public=true
                    AND dataset.source=:source
                  LIMIT 1
                """),
                {**mapping, "metric_key": metric_key},
            )
        ).mappings().first()
        if metric is None:
            return None
        rows = (
            await session.execute(
                text("""
                  SELECT period_start,value_numeric,value_text
                  FROM statistical_observations
                  WHERE metric_id=:metric_id AND statistical_area_id=:target_id
                  ORDER BY period_start
                """),
                {"metric_id": metric["id"], "target_id": mapping["target_id"]},
            )
        ).mappings().all()
        return AreaStatisticSeries(
            area=_statistics_area(selection.requested),
            statistics_area=_statistics_area(selection.target),
            inherited_from_parent=selection.inherited,
            source=await _statistics_source(session, str(mapping["source"])),
            metric={key: str(metric[key]) for key in ("key", "name", "unit", "category")},
            series=tuple(
                StatisticSeriesPoint(
                    period=str(row["period_start"].year),
                    period_start=row["period_start"],
                    value=row["value_numeric"],
                    suppressed=row["value_text"] == "suppressed",
                )
                for row in rows
            ),
        )
