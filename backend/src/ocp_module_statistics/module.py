"""Composition root for the installable Statistics module."""

from app.platform.modules.sdk import (
    STATISTICS_QUERY_SERVICE_ID,
    STATISTICS_QUERY_SERVICE_VERSION,
    ModuleContext,
    ModuleDefinition,
    ModulePersistenceContribution,
    StatisticsQueryPort,
    parse_manifest,
)

from ocp_module_statistics.application.query_service import SqlStatisticsQueryService
from ocp_module_statistics.persistence import ADOPTED_TABLES, METADATA

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "statistics",
        "name": "Statistics",
        "version": "0.2.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.15.0,<2.0.0"},
        "backend": {"package": "ocp-module-statistics"},
        "frontend": {"package": "@open-city-planner/statistics"},
        "capabilities": ["statistics.query"],
        "persistence": {"schema": "statistics", "migrations": False},
    },
    origin=__name__,
)


class StatisticsModule:
    manifest = MANIFEST

    def register(self, context: ModuleContext) -> None:
        """Publish the read-only statistics query implementation."""
        if context.services is None:
            raise RuntimeError("The Statistics module requires the service registry.")
        context.services.register(
            StatisticsQueryPort,
            SqlStatisticsQueryService(),
            service_id=STATISTICS_QUERY_SERVICE_ID,
            version=STATISTICS_QUERY_SERVICE_VERSION,
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
)
