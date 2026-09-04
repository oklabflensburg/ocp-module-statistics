from types import SimpleNamespace

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
    def __init__(
        self,
        services=...,
        *,
        enabled: bool = False,
        scheduler=...,
        database=...,
        http=...,
    ) -> None:
        self.services = Services() if services is ... else services
        self.settings = SimpleNamespace(
            require=lambda _type: SimpleNamespace(
                import_enabled=enabled,
                provider_base_url=("https://statistics.example.test" if enabled else None),
                import_schedule_seconds=None,
                import_retry_count=2,
                provider_timeout_seconds=30,
            )
        )
        self.scheduler = (
            SimpleNamespace(register=lambda definition: setattr(self, "job", definition))
            if scheduler is ...
            else scheduler
        )
        self.database = object() if database is ... else database
        self.http = object() if http is ... else http


def test_module_definition_adopts_existing_statistics_tables_without_migrations() -> None:
    assert DEFINITION.manifest is MANIFEST
    assert DEFINITION.loader is StatisticsModule
    assert DEFINITION.origin == "ocp_module_statistics.module"
    assert DEFINITION.declared_id == "statistics"
    assert DEFINITION.persistence is not None
    assert DEFINITION.persistence.metadata is METADATA
    assert DEFINITION.persistence.migration_source is None
    assert (
        DEFINITION.persistence.adopted_tables
        == ADOPTED_TABLES
        == frozenset(
            {
                "external_area_mappings",
                "statistical_datasets",
                "statistical_import_runs",
                "statistical_metrics",
                "statistical_observations",
            }
        )
    )


def test_query_only_registration_needs_no_import_ports() -> None:
    context = Context(scheduler=None, database=None, http=None)
    StatisticsModule().register(context)  # type: ignore[arg-type]
    contract, implementation, service_id, version = context.services.registration
    assert contract is StatisticsQueryPort
    assert isinstance(implementation, SqlStatisticsQueryService)
    assert service_id == "statistics.query"
    assert version == 1
    assert not hasattr(context, "job")


def test_disabled_import_with_available_ports_does_not_register_job() -> None:
    context = Context()
    StatisticsModule().register(context)  # type: ignore[arg-type]
    assert not hasattr(context, "job")


def test_reenabled_import_registers_job_again() -> None:
    disabled = Context(enabled=False)
    StatisticsModule().register(disabled)  # type: ignore[arg-type]
    enabled = Context(enabled=True)
    StatisticsModule().register(enabled)  # type: ignore[arg-type]
    assert enabled.job.job_id == "statistics.import"


def test_enabled_import_requires_scheduler_database_and_http_ports() -> None:
    for missing in ("scheduler", "database", "http"):
        arguments = {missing: None, "enabled": True}
        try:
            StatisticsModule().register(Context(**arguments))  # type: ignore[arg-type]
        except RuntimeError as error:
            assert "scheduler, database, and HTTP" in str(error)
        else:
            raise AssertionError(f"missing {missing} must fail for enabled import")


def test_registration_requires_service_registry() -> None:
    try:
        StatisticsModule().register(Context(None))  # type: ignore[arg-type]
    except RuntimeError as error:
        assert "service registry" in str(error)
    else:
        raise AssertionError("missing registry must fail")
