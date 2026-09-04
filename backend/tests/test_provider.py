import json
from contextlib import asynccontextmanager

import pytest

from ocp_module_statistics.provider import (
    DATASET_SPECS,
    ProviderError,
    ProviderTransientError,
    SupersetStatisticsProvider,
)


class Response:
    def __init__(self, status=200, *, content=b"", content_type="application/json", payload=None):
        self.status_code = status
        self.content = content
        self.headers = {"content-type": content_type}
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class Factory:
    def __init__(self, client):
        self.client = client
        self.created = []

    @asynccontextmanager
    async def create(self, *, service_name, base_url=None):
        self.created.append((service_name, base_url))
        yield self.client


def csv_response(spec, *, omit_metric=False):
    names = ["Time", *spec.dimensions]
    if not omit_metric:
        names.append(spec.metric_column)
    values = {name: "x" for name in names}
    values["Time"] = "2025-01-01"
    values["Wohnstatus"] = "Hauptwohnung"
    if "Stadtteilname" in values:
        values["Stadtteilname"] = "Altstadt"
    body = (",".join(names) + "\n" + ",".join(values[name] for name in names) + "\n").encode()
    return Response(content=body, content_type="text/csv; charset=utf-8")


def success_responses():
    return [
        Response(
            payload={
                "result": {"dashboard_title": "Zahlenspiegel", "changed_on": "2026-08-06T10:00:00Z"}
            }
        ),
        Response(payload={"result": [{} for _ in range(27)]}),
        Response(payload={"result": [{"id": spec.id} for spec in DATASET_SPECS]}),
        *(csv_response(spec) for spec in DATASET_SPECS),
    ]


@pytest.mark.asyncio
async def test_provider_success_uses_host_http_port() -> None:
    client = Client(success_responses())
    factory = Factory(client)
    result = await SupersetStatisticsProvider(
        factory,
        base_url="https://statistics.example.test",
        dashboard_id="dashboard",
        timeout_seconds=1,
    ).fetch_dataset()
    assert set(result.rows) == {6, 7, 8, 9, 10}
    assert factory.created == [("statistics-superset", "https://statistics.example.test/")]
    assert len(client.requests) == 8
    assert json.loads(client.requests[3][2]["content"])["datasource"]["id"] == 6


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "error"),
    [
        (TimeoutError(), ProviderTransientError),
        (Response(503), ProviderTransientError),
        (Response(403), ProviderError),
    ],
)
async def test_provider_classifies_transport_and_http_failures(response, error) -> None:
    provider = SupersetStatisticsProvider(
        Factory(Client([response])),
        base_url="https://statistics.example.test",
        dashboard_id="dashboard",
        timeout_seconds=1,
    )
    with pytest.raises(error):
        await provider.fetch_dataset()


@pytest.mark.asyncio
async def test_provider_rejects_malformed_json() -> None:
    response = Response(payload=ValueError("bad json"))
    provider = SupersetStatisticsProvider(
        Factory(Client([response])),
        base_url="https://statistics.example.test",
        dashboard_id="dashboard",
        timeout_seconds=1,
    )
    with pytest.raises(ProviderError, match="Malformed JSON"):
        await provider.fetch_dataset()


@pytest.mark.asyncio
async def test_provider_rejects_missing_csv_fields() -> None:
    responses = success_responses()
    responses[3] = csv_response(DATASET_SPECS[0], omit_metric=True)
    provider = SupersetStatisticsProvider(
        Factory(Client(responses)),
        base_url="https://statistics.example.test",
        dashboard_id="dashboard",
        timeout_seconds=1,
    )
    with pytest.raises(ProviderError, match="schema drift"):
        await provider.fetch_dataset()
