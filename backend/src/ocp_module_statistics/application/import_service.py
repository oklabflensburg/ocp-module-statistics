"""Import orchestration, retry classification, and module observability."""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urljoin

from app.platform.modules.sdk import ModuleContext

from ocp_module_statistics.persistence.repository import ImportReport, StatisticsRepository
from ocp_module_statistics.provider import ProviderTransientError, SupersetStatisticsProvider
from ocp_module_statistics.settings import StatisticsSettings
from ocp_module_statistics.validation import validate_and_map


class StatisticsImportService:
    def __init__(self, repository: StatisticsRepository | None = None) -> None:
        self._repository = repository or StatisticsRepository()

    async def run(self, context: ModuleContext) -> ImportReport | None:
        if context.settings is None or context.database is None or context.http is None:
            raise RuntimeError("Statistics import requires settings, database, and HTTP ports")
        settings = context.settings.require(StatisticsSettings)
        if not settings.import_enabled:
            context.logger.info("Statistics import disabled", extra={"job_phase": "disabled"})
            return None
        if settings.import_dataset != "flensburg-superset-v1":
            raise ValueError("Unsupported Statistics import dataset")
        if settings.provider_base_url is None:
            raise RuntimeError("Enabled Statistics import requires provider_base_url")
        base_url = str(settings.provider_base_url)
        source_url = urljoin(base_url, f"superset/dashboard/{settings.provider_dashboard_id}/")
        provider = SupersetStatisticsProvider(
            context.http,
            base_url=base_url,
            dashboard_id=settings.provider_dashboard_id,
            timeout_seconds=settings.provider_timeout_seconds,
        )
        started = time.perf_counter()
        context.logger.info("Statistics import started", extra={"dataset": settings.import_dataset})
        with context.observability.tracer.span(
            "statistics.import", attributes={"statistics.dataset": settings.import_dataset}
        ) as span:
            async with context.database.session() as session:
                run_id = await self._repository.start_run(session, source_url)
                try:
                    provider_dataset = await self._fetch_with_retry(
                        provider, settings.import_retry_count, context
                    )
                    canonical = validate_and_map(provider_dataset)
                    report = await self._repository.write_import(
                        session, run_id, canonical, source_url
                    )
                except Exception as exc:
                    span.record_exception(exc)
                    await self._repository.fail_run(session, run_id, exc)
                    context.observability.metrics.increment(
                        "statistics.import.failure",
                        attributes={"failure_class": type(exc).__name__},
                    )
                    context.logger.error(
                        "Statistics import failed",
                        extra={"failure_class": type(exc).__name__},
                    )
                    raise
        duration = time.perf_counter() - started
        context.observability.metrics.increment(
            "statistics.import.rows", value=report.inserted + report.updated
        )
        context.observability.metrics.observe("statistics.import.duration", duration)
        context.logger.info(
            "Statistics import succeeded",
            extra={
                "duration_seconds": duration,
                "imported_rows": report.inserted,
                "updated_rows": report.updated,
                "unchanged_rows": report.unchanged,
            },
        )
        return report

    @staticmethod
    async def _fetch_with_retry(
        provider: SupersetStatisticsProvider,
        retry_count: int,
        context: ModuleContext,
    ):
        for attempt in range(retry_count + 1):
            try:
                return await provider.fetch_dataset()
            except ProviderTransientError:
                if attempt == retry_count:
                    raise
                delay = min(2**attempt, 30)
                context.logger.info(
                    "Statistics provider retry scheduled",
                    extra={"attempt": attempt + 1, "retry_delay_seconds": delay},
                )
                await asyncio.sleep(delay)
        raise AssertionError("retry loop must return or raise")
