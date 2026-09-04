"""Minimal public SDK stand-in for standalone module unit tests."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import Any, Protocol

from fastapi import Request
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import app.platform.modules.sdk  # noqa: F401
except ModuleNotFoundError:
    app_module = ModuleType("app")
    platform_module = ModuleType("app.platform")
    modules_module = ModuleType("app.platform.modules")
    sdk_module = ModuleType("app.platform.modules.sdk")

    @dataclass(frozen=True, slots=True)
    class Manifest:
        id: str
        name: str
        version: str
        requires: dict[str, Any]
        backend: dict[str, str] | None = None
        frontend: dict[str, str] | None = None
        capabilities: tuple[str, ...] = ()
        permissions: tuple[str, ...] = ()
        config: object | None = None
        persistence: object | None = None

    def parse_manifest(data: dict[str, Any], *, origin: str | None = None) -> Manifest:
        del origin
        persistence = data.get("persistence")
        return Manifest(
            id=data["id"],
            name=data["name"],
            version=data["version"],
            requires=data["requires"],
            backend=data.get("backend"),
            frontend=data.get("frontend"),
            capabilities=tuple(data.get("capabilities", ())),
            permissions=tuple(data.get("permissions", ())),
            config=SimpleNamespace(**data["config"]) if data.get("config") else None,
            persistence=SimpleNamespace(**persistence) if persistence else None,
        )

    @dataclass(frozen=True, slots=True)
    class ModulePersistenceContribution:
        module_id: str
        metadata: MetaData
        schema: str
        migration_source: object | None = None
        adopted_tables: frozenset[str] = frozenset()

    @dataclass(frozen=True, slots=True)
    class ModuleDefinition:
        manifest: Manifest
        loader: type
        origin: str
        declared_id: str
        persistence: ModulePersistenceContribution | None = None
        settings: object | None = None

    @dataclass(frozen=True, slots=True)
    class ModuleSettingsContribution:
        module_id: str
        namespace: str
        model: type

    @dataclass(frozen=True, slots=True)
    class JobSchedule:
        interval_seconds: int

    @dataclass(frozen=True, slots=True)
    class RetryPolicy:
        max_attempts: int = 1

    @dataclass(frozen=True, slots=True)
    class JobDefinition:
        job_id: str
        handler: object
        retry: RetryPolicy = RetryPolicy()
        timeout_seconds: float | None = None
        schedule: JobSchedule | None = None
        allow_concurrent_runs: bool = False

    class ModuleContext:
        pass

    @dataclass(frozen=True, slots=True)
    class ModulePrincipal:
        id: str

    class DatabaseSessionProvider(Protocol):
        def session(self): ...

    class PublicQueryPort(Protocol):
        async def guard(self, request: Request, session: AsyncSession, resource: str): ...

    class PermissionDependencyFactory(Protocol):
        def require(self, permission_id: str, *, csrf: bool = False): ...

    class HttpClientPort(Protocol):
        pass

    class HttpClientFactoryPort(Protocol):
        pass

    class StatisticsQueryPort(Protocol):
        pass

    @dataclass(frozen=True, slots=True)
    class StatisticsArea:
        id: object
        slug: str
        name: str
        area_type: str

    @dataclass(frozen=True, slots=True)
    class StatisticsSelection:
        requested: StatisticsArea
        target: StatisticsArea
        municipality: StatisticsArea
        inherited: bool = False

    @dataclass(frozen=True, slots=True)
    class StatisticsSource:
        name: str
        url: str
        license: str
        source_updated_at: object | None
        last_import_at: object | None

    @dataclass(frozen=True, slots=True)
    class StatisticValue:
        key: str
        name: str
        category: str
        value: object | None
        unit: str
        period: str
        period_start: object
        area_level: str
        is_calculated: bool
        municipality_value: object | None = None
        difference: object | None = None
        relative_difference: object | None = None

    @dataclass(frozen=True, slots=True)
    class AreaStatistics:
        area: StatisticsArea
        statistics_area: StatisticsArea
        inherited_from_parent: bool
        source: StatisticsSource | None
        latest: tuple[StatisticValue, ...] = ()

    @dataclass(frozen=True, slots=True)
    class StatisticSeriesPoint:
        period: str
        period_start: object
        value: object | None
        suppressed: bool

    @dataclass(frozen=True, slots=True)
    class AreaStatisticSeries:
        area: StatisticsArea
        statistics_area: StatisticsArea
        inherited_from_parent: bool
        source: StatisticsSource | None
        metric: dict[str, str]
        series: tuple[StatisticSeriesPoint, ...] = ()

    exports = locals()
    for name in (
        "AreaStatistics",
        "AreaStatisticSeries",
        "DatabaseSessionProvider",
        "HttpClientFactoryPort",
        "HttpClientPort",
        "JobDefinition",
        "JobSchedule",
        "ModuleContext",
        "ModuleDefinition",
        "ModulePersistenceContribution",
        "ModulePrincipal",
        "ModuleSettingsContribution",
        "PermissionDependencyFactory",
        "PublicQueryPort",
        "RetryPolicy",
        "StatisticSeriesPoint",
        "StatisticsArea",
        "StatisticsQueryPort",
        "StatisticsSelection",
        "StatisticsSource",
        "StatisticValue",
        "parse_manifest",
    ):
        setattr(sdk_module, name, exports[name])
    sdk_module.STATISTICS_QUERY_SERVICE_ID = "statistics.query"
    sdk_module.STATISTICS_QUERY_SERVICE_VERSION = 1
    sys.modules.update(
        {
            "app": app_module,
            "app.platform": platform_module,
            "app.platform.modules": modules_module,
            "app.platform.modules.sdk": sdk_module,
        }
    )
