"""Small Superset provider adapter using only the public Host HTTP port."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.platform.modules.sdk import HttpClientFactoryPort, HttpClientPort


class ProviderError(RuntimeError):
    """A non-retryable provider response or contract failure."""


class ProviderTransientError(ProviderError):
    """A timeout, connection failure, or temporary upstream response."""


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    id: int
    name: str
    metric_column: str
    dimensions: tuple[str, ...]


DATASET_SPECS = (
    DatasetSpec(
        6,
        "STK_RESULTS_Sozialatlas_01",
        "Anzahl",
        (
            "Wohnstatus",
            "Migrationshintergrund",
            "Altersgruppe",
            "Familienstand",
            "Stadtteilname",
        ),
    ),
    DatasetSpec(
        7,
        "STK_RESULTS_Haushalte_AnzahlPersonenHaushalt",
        "AnzahlHaushalte",
        (
            "Wohnstatus",
            "ZahlPersonenHaushalt",
            "Stadtteilname",
        ),
    ),
    DatasetSpec(
        8,
        "STK_RESULTS_Haushalte_Migrationshintergrund",
        "AnzahlHaushalte",
        (
            "Wohnstatus",
            "Migrationshintergrund_Haushalte",
            "Stadtteilname",
        ),
    ),
    DatasetSpec(
        9,
        "STK_RESULTS_Haushalte_ZahlKinderHaushalt",
        "AnzahlHaushalte",
        (
            "Wohnstatus",
            "ZahlKinderHaushalt",
            "Stadtteilname",
        ),
    ),
    DatasetSpec(10, "STK_RESULTS_Haushalte_Haushaltstyp", "AnzahlHaushalte", ("Wohnstatus",)),
)


@dataclass(frozen=True, slots=True)
class ProviderDataset:
    source_updated_at: datetime
    rows: dict[int, tuple[dict[str, str], ...]]
    raw_parts: tuple[bytes, ...]
    column_names: dict[int, tuple[str, ...]]


class SupersetStatisticsProvider:
    def __init__(
        self,
        factory: HttpClientFactoryPort,
        *,
        base_url: str,
        dashboard_id: str,
        timeout_seconds: float,
    ) -> None:
        self._factory = factory
        self._base_url = base_url.rstrip("/") + "/"
        self._dashboard_id = dashboard_id
        self._timeout_seconds = timeout_seconds

    async def fetch_dataset(self) -> ProviderDataset:
        async with self._factory.create(
            service_name="statistics-superset", base_url=self._base_url
        ) as client:
            dashboard = self._result_object(
                await self._json(client, "GET", f"api/v1/dashboard/{self._dashboard_id}"),
                "dashboard",
            )
            if dashboard.get("dashboard_title") != "Zahlenspiegel":
                raise ProviderError("Unexpected dashboard identity")
            charts = self._result_list(
                await self._json(client, "GET", f"api/v1/dashboard/{self._dashboard_id}/charts"),
                "chart inventory",
            )
            datasets = self._result_list(
                await self._json(client, "GET", f"api/v1/dashboard/{self._dashboard_id}/datasets"),
                "dataset inventory",
            )
            try:
                inventory_ids = {int(item["id"]) for item in datasets}
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderError("Malformed dataset inventory") from exc
            expected_ids = {spec.id for spec in DATASET_SPECS}
            if inventory_ids != expected_ids or len(charts) != 27:
                raise ProviderError("Superset inventory drift")
            source_updated_at = self._timestamp(dashboard.get("changed_on"))
            rows: dict[int, tuple[dict[str, str], ...]] = {}
            raw_parts: list[bytes] = []
            columns: dict[int, tuple[str, ...]] = {}
            for spec in DATASET_SPECS:
                body, parsed, names = await self._download(client, spec)
                raw_parts.append(str(spec.id).encode() + b"\0" + body)
                rows[spec.id] = parsed
                columns[spec.id] = names
            return ProviderDataset(source_updated_at, rows, tuple(raw_parts), columns)

    async def _download(
        self, client: HttpClientPort, spec: DatasetSpec
    ) -> tuple[bytes, tuple[dict[str, str], ...], tuple[str, ...]]:
        query = {
            "datasource": {"id": spec.id, "type": "table"},
            "force": False,
            "queries": [
                {
                    "time_range": "No filter",
                    "granularity": "Jahr",
                    "filters": [],
                    "extras": {"time_grain_sqla": "P1Y", "having": "", "where": ""},
                    "applied_time_extras": {},
                    "columns": list(spec.dimensions),
                    "metrics": [
                        {
                            "expressionType": "SIMPLE",
                            "column": {"column_name": spec.metric_column},
                            "aggregate": "SUM",
                            "label": spec.metric_column,
                        }
                    ],
                    "orderby": [],
                    "annotation_layers": [],
                    "row_limit": 100_000,
                    "order_desc": False,
                    "is_timeseries": True,
                    "time_offsets": [],
                    "post_processing": [],
                }
            ],
            "result_format": "csv",
            "result_type": "full",
        }
        response = await self._request(
            client,
            "POST",
            "api/v1/chart/data",
            headers={"Content-Type": "application/json"},
            content=json.dumps(query, separators=(",", ":")).encode(),
        )
        content_type = response.headers.get("content-type", "").lower()
        if "csv" not in content_type or response.content.lstrip().lower().startswith(b"<!doctype"):
            raise ProviderError(f"Dataset {spec.id} did not return CSV")
        try:
            text = response.content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text, newline=""))
            parsed = tuple(dict(row) for row in reader)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise ProviderError(f"Dataset {spec.id} is not valid UTF-8 CSV") from exc
        expected = ("Time", *spec.dimensions, spec.metric_column)
        names = tuple(reader.fieldnames or ())
        if set(names) != set(expected) or len(names) != len(expected):
            raise ProviderError(f"Dataset {spec.id} schema drift")
        if not parsed:
            raise ProviderError(f"Dataset {spec.id} returned no rows")
        return response.content, parsed, names

    async def _json(self, client: HttpClientPort, method: str, endpoint: str) -> dict[str, Any]:
        response = await self._request(client, method, endpoint)
        if "json" not in response.headers.get("content-type", "").lower():
            raise ProviderError(f"Expected JSON from {endpoint}")
        try:
            payload = response.json()
        except Exception as exc:
            raise ProviderError(f"Malformed JSON from {endpoint}") from exc
        if not isinstance(payload, dict):
            raise ProviderError(f"Unexpected JSON from {endpoint}")
        return payload

    async def _request(self, client: HttpClientPort, method: str, endpoint: str, **kwargs: Any):
        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await client.request(method, endpoint, **kwargs)
        except TimeoutError as exc:
            raise ProviderTransientError(f"Provider timeout for {endpoint}") from exc
        except ValueError as exc:
            raise ProviderError(f"Invalid provider request for {endpoint}") from exc
        except Exception as exc:
            raise ProviderTransientError(f"Provider connection failed for {endpoint}") from exc
        if 500 <= response.status_code <= 599:
            raise ProviderTransientError(f"Provider temporary HTTP {response.status_code}")
        if response.status_code != 200:
            raise ProviderError(f"Provider HTTP {response.status_code}")
        return response

    @staticmethod
    def _result_object(payload: dict[str, Any], label: str) -> dict[str, Any]:
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ProviderError(f"Unexpected {label}")
        return result

    @staticmethod
    def _result_list(payload: dict[str, Any], label: str) -> list[dict[str, Any]]:
        result = payload.get("result")
        if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
            raise ProviderError(f"Unexpected {label}")
        return result

    @staticmethod
    def _timestamp(value: object) -> datetime:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise ProviderError("Invalid provider update timestamp") from exc
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
