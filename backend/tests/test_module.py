from app.platform.modules.sdk import StatisticsQueryPort

from ocp_module_statistics.application.query_service import SqlStatisticsQueryService
from ocp_module_statistics.module import DEFINITION, MANIFEST, StatisticsModule
from ocp_module_statistics.persistence import ADOPTED_TABLES, METADATA


class Services:
    def __init__(self) -> None:
        self.registration = None

    def register(self, contract, implementation, *, service_id: str, version: int) -> None:
        self.registration = (contract, implementation, service_id, version)


class Context:
    def __init__(self, services=...) -> None:
        self.services = Services() if services is ... else services


def test_module_definition_adopts_existing_statistics_tables_without_migrations() -> None:
    assert DEFINITION.manifest is MANIFEST
    assert DEFINITION.loader is StatisticsModule
    assert DEFINITION.origin == "ocp_module_statistics.module"
    assert DEFINITION.declared_id == "statistics"
    assert DEFINITION.persistence is not None
    assert DEFINITION.persistence.metadata is METADATA
    assert DEFINITION.persistence.migration_source is None
    assert DEFINITION.persistence.adopted_tables == ADOPTED_TABLES == frozenset(
        {
            "external_area_mappings",
            "statistical_datasets",
            "statistical_import_runs",
            "statistical_metrics",
            "statistical_observations",
        }
    )


def test_registration_publishes_statistics_query_port() -> None:
    context = Context()
    StatisticsModule().register(context)  # type: ignore[arg-type]
    contract, implementation, service_id, version = context.services.registration
    assert contract is StatisticsQueryPort
    assert isinstance(implementation, SqlStatisticsQueryService)
    assert service_id == "statistics.query"
    assert version == 1


def test_registration_requires_service_registry() -> None:
    try:
        StatisticsModule().register(Context(None))  # type: ignore[arg-type]
    except RuntimeError as error:
        assert "service registry" in str(error)
    else:
        raise AssertionError("missing registry must fail")
