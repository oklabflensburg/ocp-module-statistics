"""Composition root for the installable Statistics module."""

from app.platform.modules.sdk import (
    STATISTICS_QUERY_SERVICE_ID,
    STATISTICS_QUERY_SERVICE_VERSION,
    JobDefinition,
    JobSchedule,
    ModuleContext,
    ModuleDefinition,
    ModulePersistenceContribution,
    ModuleSettingsContribution,
    StatisticsQueryPort,
    parse_manifest,
)

from ocp_module_statistics.application.import_service import StatisticsImportService
from ocp_module_statistics.application.query_service import SqlStatisticsQueryService
from ocp_module_statistics.persistence import ADOPTED_TABLES, METADATA
from ocp_module_statistics.settings import StatisticsSettings

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "statistics",
        "name": "Statistics",
        "version": "0.3.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.15.0,<2.0.0"},
        "backend": {"package": "ocp-module-statistics"},
        "frontend": {"package": "@open-city-planner/statistics"},
        "capabilities": ["statistics.query", "statistics.import"],
        "config": {"namespace": "statistics"},
        "persistence": {"schema": "statistics", "migrations": False},
    },
    origin=__name__,
)


class StatisticsModule:
    manifest = MANIFEST

    def register(self, context: ModuleContext) -> None:
        """Publish queries and, when enabled, the module-owned import job."""
        if context.services is None:
            raise RuntimeError("The Statistics module requires the service registry.")
        context.services.register(
            StatisticsQueryPort,
            SqlStatisticsQueryService(),
            service_id=STATISTICS_QUERY_SERVICE_ID,
            version=STATISTICS_QUERY_SERVICE_VERSION,
        )
        if context.settings is None:
            raise RuntimeError("The Statistics module requires module settings.")
        settings = context.settings.require(StatisticsSettings)
        if not settings.import_enabled:
            return
        if context.scheduler is None or context.database is None or context.http is None:
            raise RuntimeError(
                "The Statistics import requires scheduler, database, and HTTP ports."
            )
        schedule = (
            JobSchedule(interval_seconds=settings.import_schedule_seconds)
            if settings.import_schedule_seconds is not None
            else None
        )
        context.scheduler.register(
            JobDefinition(
                job_id="statistics.import",
                handler=StatisticsImportService().run,
                timeout_seconds=min(
                    settings.provider_timeout_seconds
                    * len(range(settings.import_retry_count + 1))
                    * 8
                    + 30,
                    3600,
                ),
                schedule=schedule,
            )
        )


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=StatisticsModule,
    origin=__name__,
    declared_id=MANIFEST.id,
    persistence=ModulePersistenceContribution(
        module_id=MANIFEST.id,
        metadata=METADATA,
        schema="statistics",
        adopted_tables=ADOPTED_TABLES,
    ),
    settings=ModuleSettingsContribution(
        module_id=MANIFEST.id,
        namespace="statistics",
        model=StatisticsSettings,
    ),
)
