from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

from app.platform.modules.sdk import ModulePrincipal
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from ocp_module_statistics.api.router import create_router

NOW = datetime(2026, 9, 4, 10, 30, tzinfo=UTC)


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class CatalogSession:
    def __init__(self):
        self.calls = []
        self.rollbacks = 0

    async def scalar(self, statement, parameters=None):
        sql = str(statement).lower()
        self.calls.append((sql, parameters or {}))
        if "from statistical_metrics" in sql:
            return 1
        if "from statistical_import_runs" in sql:
            return 1
        raise AssertionError(sql)

    async def execute(self, statement, parameters=None):
        sql = str(statement).lower()
        parameters = parameters or {}
        self.calls.append((sql, parameters))
        if "from statistical_datasets" in sql:
            return Result(
                [
                    {
                        "source": "superset",
                        "external_dataset_id": "1",
                        "name": "Bevölkerung",
                        "description": "Veröffentlichter Datensatz",
                        "source_url": "https://example.test/source",
                        "license": "Datenlizenz Deutschland – Namensnennung – 2.0",
                        "update_frequency": "annual",
                        "last_import_at": NOW,
                        "source_updated_at": NOW,
                    }
                ]
            )
        if "from statistical_metrics" in sql:
            return Result(
                [
                    {
                        "key": "population",
                        "name": "Bevölkerung",
                        "description": "Einwohnerinnen und Einwohner",
                        "category": "Bevölkerung",
                        "unit": "persons",
                        "value_type": "numeric",
                        "aggregation_method": "SUM",
                        "public": True,
                        "source": "superset",
                        "dataset": "1",
                        "dataset_name": "Bevölkerung",
                    }
                ]
            )
        if "from statistical_import_runs" in sql:
            return Result(
                [
                    {
                        "id": 7,
                        "source": "superset",
                        "started_at": NOW,
                        "finished_at": NOW,
                        "status": "FAILED",
                        "rows_downloaded": 10,
                        "rows_imported": 0,
                        "rows_updated": 0,
                        "rows_unchanged": 0,
                        "rows_rejected": 10,
                        "error_message": "x" * 800,
                    }
                ]
            )
        raise AssertionError(sql)

    async def rollback(self):
        self.rollbacks += 1


class Database:
    def __init__(self, session):
        self.value = session

    @asynccontextmanager
    async def session(self):
        yield self.value


class PublicQueries:
    limits = SimpleNamespace(max_response_items=2)

    def __init__(self):
        self.resources = []

    async def guard(self, _request, _session, resource):
        self.resources.append(resource)

    def is_timeout(self, _error):
        return False


class Permissions:
    def __init__(self, *, allowed):
        self.allowed = allowed
        self.requirements = []

    def require(self, permission_id, *, csrf=False):
        self.requirements.append((permission_id, csrf))

        async def dependency():
            if not self.allowed:
                raise HTTPException(403, "Berechtigung fehlt.")
            return ModulePrincipal(id="operator")

        return dependency


def client(*, allowed=True, import_enabled=True):
    session = CatalogSession()
    public_queries = PublicQueries()
    permissions = Permissions(allowed=allowed)
    app = FastAPI()
    app.include_router(
        create_router(
            Database(session),
            public_queries,
            permissions,
            import_enabled=import_enabled,
        ),
        prefix="/api/v1",
    )
    return TestClient(app), session, public_queries, permissions


def test_public_sources_return_only_statistics_owned_dto() -> None:
    http, _session, queries, _permissions = client()
    response = http.get("/api/v1/statistics/sources")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.json()[0] == {
        "source": "superset",
        "dataset": "1",
        "name": "Bevölkerung",
        "description": "Veröffentlichter Datensatz",
        "source_url": "https://example.test/source",
        "license": "Datenlizenz Deutschland – Namensnennung – 2.0",
        "update_frequency": "annual",
        "last_import_at": "2026-09-04T10:30:00Z",
        "source_updated_at": "2026-09-04T10:30:00Z",
    }
    assert queries.resources == ["statistics-sources"]


def test_public_metrics_filter_and_bound_pagination() -> None:
    http, session, queries, _permissions = client()
    response = http.get(
        "/api/v1/statistics/metrics",
        params={"query": "100%_", "category": " Bevölkerung ", "source": " SUPERSET ", "limit": 99},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["limit"] == 2
    count_sql, parameters = next(
        call for call in session.calls if "count(*)" in call[0] and "statistical_metrics" in call[0]
    )
    assert "metric.public=true" in count_sql
    assert parameters["query"] == "%100\\%\\_%"
    assert parameters["category"] == "bevölkerung"
    assert parameters["source"] == "superset"
    assert queries.resources == ["statistics-metrics"]


def test_import_routes_require_permission_and_hide_provider_details() -> None:
    denied, _session, _queries, permissions = client(allowed=False)
    assert denied.get("/api/v1/statistics/import-status").status_code == 403
    assert denied.get("/api/v1/statistics/import-runs").status_code == 403
    assert permissions.requirements == [("statistics.import", False)]

    allowed, _session, _queries, _permissions = client(allowed=True)
    status = allowed.get("/api/v1/statistics/import-status")
    runs = allowed.get("/api/v1/statistics/import-runs?limit=99")
    assert status.status_code == runs.status_code == 200
    assert status.headers["cache-control"] == "private, no-store"
    assert status.json()["last_run"]["error_summary"] == "x" * 500
    assert runs.json()["limit"] == 2
    assert "source_url" not in runs.json()["items"][0]
    assert "checksum" not in runs.json()["items"][0]


def test_disabled_import_has_clear_status() -> None:
    http, _session, _queries, _permissions = client(import_enabled=False)
    response = http.get("/api/v1/statistics/import-status")
    assert response.status_code == 200
    assert response.json()["import_enabled"] is False
    assert response.json()["job_available"] is False
