"""Transactional writes restricted to the five Statistics-owned tables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ocp_module_statistics.provider import DATASET_SPECS
from ocp_module_statistics.validation import (
    AREA_MAPPING,
    LICENSE,
    METRICS,
    SOURCE,
    CanonicalImport,
    ImportValidationError,
)


@dataclass(frozen=True, slots=True)
class ImportReport:
    status: str
    rows_downloaded: int
    inserted: int
    updated: int
    unchanged: int
    rejected: int
    checksum: str


class StatisticsRepository:
    async def start_run(self, session: AsyncSession, source_url: str) -> int:
        run_id = await session.scalar(
            text("""
            INSERT INTO statistical_import_runs (
              source,started_at,status,rows_downloaded,rows_imported,rows_updated,
              rows_unchanged,rows_rejected,source_url
            ) VALUES (
              :source,:started_at,'RUNNING',0,0,0,0,0,:source_url
            ) RETURNING id
        """),
            {"source": SOURCE, "started_at": datetime.now(UTC), "source_url": source_url},
        )
        if run_id is None:
            raise RuntimeError("Import run could not be created")
        await session.commit()
        return int(run_id)

    async def write_import(
        self,
        session: AsyncSession,
        run_id: int,
        imported: CanonicalImport,
        source_url: str,
    ) -> ImportReport:
        imported_at = datetime.now(UTC)
        mappings = await self._ensure_mappings(session)
        datasets = await self._ensure_datasets(session, imported, source_url)
        metrics = await self._ensure_metrics(session, datasets)
        existing = await self._existing_observations(session, tuple(metrics.values()))
        inserted = updated = unchanged = 0
        for observation in imported.observations:
            metric_id = metrics[observation.metric_key]
            mapping_id = mappings[observation.external_area_id]
            identity = (
                metric_id,
                mapping_id,
                observation.period_start,
                observation.external_area_id,
            )
            old_hash = existing.get(identity)
            if old_hash == observation.source_row_hash:
                unchanged += 1
                continue
            await session.execute(
                text("""
                INSERT INTO statistical_observations (
                  metric_id,statistical_area_id,period_type,period_start,period_end,
                  value_numeric,value_text,source_area_id,source_row_hash,is_calculated,
                  imported_at,source_updated_at
                ) VALUES (
                  :metric_id,:statistical_area_id,'YEAR',:period_start,:period_end,
                  :value_numeric,:value_text,:source_area_id,:source_row_hash,:is_calculated,
                  :imported_at,:source_updated_at
                ) ON CONFLICT ON CONSTRAINT uq_statistical_observation DO UPDATE SET
                  period_end=excluded.period_end,
                  value_numeric=excluded.value_numeric,
                  value_text=excluded.value_text,
                  source_row_hash=excluded.source_row_hash,
                  is_calculated=excluded.is_calculated,
                  imported_at=excluded.imported_at,
                  source_updated_at=excluded.source_updated_at
            """),
                {
                    "metric_id": metric_id,
                    "statistical_area_id": mapping_id,
                    "period_start": observation.period_start,
                    "period_end": observation.period_end,
                    "value_numeric": observation.value,
                    "value_text": "suppressed" if observation.value is None else None,
                    "source_area_id": observation.external_area_id,
                    "source_row_hash": observation.source_row_hash,
                    "is_calculated": observation.is_calculated,
                    "imported_at": imported_at,
                    "source_updated_at": imported.source_updated_at,
                },
            )
            if old_hash is None:
                inserted += 1
            else:
                updated += 1
        await session.execute(
            text("""
            UPDATE statistical_datasets
            SET last_import_at=:imported_at,updated_at=:imported_at
            WHERE source=:source
        """),
            {"imported_at": imported_at, "source": SOURCE},
        )
        await session.execute(
            text("""
            UPDATE statistical_import_runs SET
              finished_at=:finished_at,status='SUCCESS',rows_downloaded=:downloaded,
              rows_imported=:inserted,rows_updated=:updated,rows_unchanged=:unchanged,
              rows_rejected=0,checksum=:checksum,schema_hash=:schema_hash,
              column_names=:column_names,error_message=NULL
            WHERE id=:run_id AND source=:source
        """),
            {
                "finished_at": imported_at,
                "downloaded": imported.rows_downloaded,
                "inserted": inserted,
                "updated": updated,
                "unchanged": unchanged,
                "checksum": imported.checksum,
                "schema_hash": imported.schema_hash,
                "column_names": imported.column_names,
                "run_id": run_id,
                "source": SOURCE,
            },
        )
        await session.commit()
        return ImportReport(
            "SUCCESS", imported.rows_downloaded, inserted, updated, unchanged, 0, imported.checksum
        )

    async def fail_run(self, session: AsyncSession, run_id: int, error: Exception) -> None:
        await session.rollback()
        summary = f"{type(error).__name__}: {error}"[:1000]
        await session.execute(
            text("""
            UPDATE statistical_import_runs SET
              finished_at=:finished_at,status='FAILED',error_message=:summary
            WHERE id=:run_id AND source=:source
        """),
            {
                "finished_at": datetime.now(UTC),
                "summary": summary,
                "run_id": run_id,
                "source": SOURCE,
            },
        )
        await session.commit()

    async def _ensure_mappings(self, session: AsyncSession) -> dict[str, int]:
        rows = (
            (
                await session.execute(
                    text("""
            SELECT id,external_area_id,external_area_name,level
            FROM external_area_mappings WHERE source=:source
        """),
                    {"source": SOURCE},
                )
            )
            .mappings()
            .all()
        )
        by_id: dict[str, object] = {}
        by_name: dict[str, list[object]] = {}
        for row in rows:
            external_id = str(row["external_area_id"])
            by_id[external_id] = row
            by_name.setdefault(str(row["external_area_name"]), []).append(row)
        if any(len(matches) != 1 for matches in by_name.values()):
            raise ImportValidationError("Ambiguous stored area mapping")
        result: dict[str, int] = {}
        for external_id, (name, level) in AREA_MAPPING.items():
            current = by_id.get(external_id)
            if current is not None:
                if str(current["external_area_name"]) != name or str(current["level"]) != level:  # type: ignore[index]
                    raise ImportValidationError("Conflicting stored area mapping")
                result[external_id] = int(current["id"])  # type: ignore[index]
                continue
            if name in by_name:
                raise ImportValidationError("Ambiguous stored area mapping")
            mapping_id = await session.scalar(
                text("""
                INSERT INTO external_area_mappings (
                  source,external_area_id,external_area_name,level,created_at,updated_at
                ) VALUES (:source,:external_id,:name,:level,:now,:now) RETURNING id
            """),
                {
                    "source": SOURCE,
                    "external_id": external_id,
                    "name": name,
                    "level": level,
                    "now": datetime.now(UTC),
                },
            )
            if mapping_id is None:
                raise RuntimeError("Area mapping could not be created")
            result[external_id] = int(mapping_id)
        unknown = set(by_id) - set(AREA_MAPPING)
        if unknown:
            raise ImportValidationError("Unknown stored area mapping")
        return result

    async def _ensure_datasets(
        self, session: AsyncSession, imported: CanonicalImport, source_url: str
    ) -> dict[int, int]:
        result: dict[int, int] = {}
        for spec in DATASET_SPECS:
            dataset_id = await session.scalar(
                text("""
                INSERT INTO statistical_datasets (
                  source,external_dataset_id,name,source_url,license,update_frequency,
                  source_updated_at,created_at,updated_at
                ) VALUES (
                  :source,:external_id,:name,:source_url,:license,:frequency,
                  :source_updated_at,:now,:now
                ) ON CONFLICT ON CONSTRAINT uq_statistical_dataset_source DO UPDATE SET
                  name=excluded.name,source_url=excluded.source_url,license=excluded.license,
                  update_frequency=excluded.update_frequency,
                  source_updated_at=excluded.source_updated_at,updated_at=excluded.updated_at
                RETURNING id
            """),
                {
                    "source": SOURCE,
                    "external_id": str(spec.id),
                    "name": spec.name,
                    "source_url": source_url,
                    "license": LICENSE,
                    "frequency": "annual; checked manually",
                    "source_updated_at": imported.source_updated_at,
                    "now": datetime.now(UTC),
                },
            )
            if dataset_id is None:
                raise RuntimeError("Dataset could not be created")
            result[spec.id] = int(dataset_id)
        return result

    async def _ensure_metrics(
        self, session: AsyncSession, datasets: dict[int, int]
    ) -> dict[str, int]:
        result: dict[str, int] = {}
        for metric in METRICS:
            metric_id = await session.scalar(
                text("""
                INSERT INTO statistical_metrics (
                  dataset_id,key,name,description,unit,value_type,category,
                  aggregation_method,public,created_at,updated_at
                ) VALUES (
                  :dataset_id,:key,:name,:description,:unit,'numeric',:category,
                  'SUM',true,:now,:now
                ) ON CONFLICT (key) DO UPDATE SET
                  dataset_id=excluded.dataset_id,name=excluded.name,
                  description=excluded.description,unit=excluded.unit,
                  value_type=excluded.value_type,category=excluded.category,
                  aggregation_method=excluded.aggregation_method,public=excluded.public,
                  updated_at=excluded.updated_at
                RETURNING id
            """),
                {
                    "dataset_id": datasets[metric.dataset_id],
                    "key": metric.key,
                    "name": metric.name,
                    "description": metric.description,
                    "unit": metric.unit,
                    "category": metric.category,
                    "now": datetime.now(UTC),
                },
            )
            if metric_id is None:
                raise RuntimeError("Metric could not be created")
            result[metric.key] = int(metric_id)
        return result

    async def _existing_observations(
        self, session: AsyncSession, metric_ids: tuple[int, ...]
    ) -> dict[tuple[int, int, object, str], str]:
        if not metric_ids:
            return {}
        rows = (
            (
                await session.execute(
                    text("""
            SELECT metric_id,statistical_area_id,period_start,source_area_id,source_row_hash
            FROM statistical_observations
            WHERE metric_id = ANY(:metric_ids)
        """),
                    {"metric_ids": list(metric_ids)},
                )
            )
            .mappings()
            .all()
        )
        return {
            (
                int(row["metric_id"]),
                int(row["statistical_area_id"]),
                row["period_start"],
                str(row["source_area_id"]),
            ): str(row["source_row_hash"])
            for row in rows
        }
