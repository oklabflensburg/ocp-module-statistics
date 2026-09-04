"""Statistics-owned public and operator HTTP routes."""

from collections.abc import AsyncIterator
from typing import Annotated, NoReturn

from app.platform.modules.sdk import (
    DatabaseSessionProvider,
    ModulePrincipal,
    PermissionDependencyFactory,
    PublicQueryPort,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from ocp_module_statistics.api.schemas import (
    StatisticsImportRunPageDto,
    StatisticsImportStatusDto,
    StatisticsMetricPageDto,
    StatisticsSourceDto,
)
from ocp_module_statistics.application.catalog_service import StatisticsCatalogService


def create_router(
    database: DatabaseSessionProvider,
    public_queries: PublicQueryPort,
    permission_dependencies: PermissionDependencyFactory,
    *,
    import_enabled: bool,
) -> APIRouter:
    router = APIRouter(prefix="/statistics", tags=["Statistics"])
    service = StatisticsCatalogService()
    maximum_items = public_queries.limits.max_response_items
    default_limit = min(50, maximum_items)
    require_import = permission_dependencies.require("statistics.import")

    async def session_dependency() -> AsyncIterator[AsyncSession]:
        async with database.session() as session:
            yield session

    SessionDep = Annotated[AsyncSession, Depends(session_dependency)]
    ImportPrincipalDep = Annotated[ModulePrincipal, Depends(require_import)]

    async def raise_database_error(session: AsyncSession, error: DBAPIError) -> NoReturn:
        if not public_queries.is_timeout(error):
            raise error
        await session.rollback()
        raise HTTPException(503, "Der Statistikdienst ist vorübergehend nicht verfügbar.") from error

    @router.get("/sources", response_model=list[StatisticsSourceDto])
    async def get_sources(
        request: Request, response: Response, session: SessionDep
    ) -> list[StatisticsSourceDto]:
        await public_queries.guard(request, session, "statistics-sources")
        response.headers["Cache-Control"] = "public, max-age=300"
        try:
            return await service.sources(session, limit=maximum_items)
        except DBAPIError as error:
            await raise_database_error(session, error)

    @router.get("/metrics", response_model=StatisticsMetricPageDto)
    async def get_metrics(
        request: Request,
        response: Response,
        session: SessionDep,
        query: Annotated[str | None, Query(max_length=120)] = None,
        category: Annotated[str | None, Query(max_length=80)] = None,
        source: Annotated[str | None, Query(max_length=40)] = None,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1)] = default_limit,
    ) -> StatisticsMetricPageDto:
        await public_queries.guard(request, session, "statistics-metrics")
        response.headers["Cache-Control"] = "public, max-age=300"
        try:
            return await service.metrics(
                session,
                query=query.strip() if query and query.strip() else None,
                category=category.strip() if category and category.strip() else None,
                source=source.strip() if source and source.strip() else None,
                offset=offset,
                limit=min(limit, maximum_items),
            )
        except DBAPIError as error:
            await raise_database_error(session, error)

    @router.get("/import-status", response_model=StatisticsImportStatusDto)
    async def get_import_status(
        response: Response,
        session: SessionDep,
        _principal: ImportPrincipalDep,
    ) -> StatisticsImportStatusDto:
        response.headers["Cache-Control"] = "private, no-store"
        try:
            return StatisticsImportStatusDto(
                import_enabled=import_enabled,
                job_available=import_enabled,
                last_run=await service.last_import_run(session),
            )
        except DBAPIError as error:
            await raise_database_error(session, error)

    @router.get("/import-runs", response_model=StatisticsImportRunPageDto)
    async def get_import_runs(
        response: Response,
        session: SessionDep,
        _principal: ImportPrincipalDep,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1)] = default_limit,
    ) -> StatisticsImportRunPageDto:
        response.headers["Cache-Control"] = "private, no-store"
        try:
            return await service.import_runs(
                session, offset=offset, limit=min(limit, maximum_items)
            )
        except DBAPIError as error:
            await raise_database_error(session, error)

    return router
