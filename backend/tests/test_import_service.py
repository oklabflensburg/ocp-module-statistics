from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ocp_module_statistics.application.import_service import StatisticsImportService
from ocp_module_statistics.provider import ProviderError, ProviderTransientError


class Provider:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def fetch_dataset(self):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_retry_applies_only_to_transient_provider_failures(monkeypatch) -> None:
    transient = Provider([ProviderTransientError("temporary"), "ok"])
    context = SimpleNamespace(logger=SimpleNamespace(info=lambda *args, **kwargs: None))
    sleep = AsyncMock()
    monkeypatch.setattr("ocp_module_statistics.application.import_service.asyncio.sleep", sleep)
    assert await StatisticsImportService._fetch_with_retry(transient, 2, context) == "ok"
    assert transient.calls == 2
    sleep.assert_awaited_once_with(1)

    permanent = Provider([ProviderError("invalid")])
    with pytest.raises(ProviderError):
        await StatisticsImportService._fetch_with_retry(permanent, 2, context)
    assert permanent.calls == 1


class SessionContext:
    @asynccontextmanager
    async def session(self):
        yield object()


class Span:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def record_exception(self, _error):
        pass


class Repository:
    def __init__(self):
        self.started = AsyncMock(return_value=7)
        self.written = AsyncMock()
        self.failed = AsyncMock()

    start_run = property(lambda self: self.started)
    write_import = property(lambda self: self.written)
    fail_run = property(lambda self: self.failed)


@pytest.mark.asyncio
async def test_late_validation_failure_never_calls_write_service(monkeypatch) -> None:
    repository = Repository()
    service = StatisticsImportService(repository)  # type: ignore[arg-type]
    service._fetch_with_retry = AsyncMock(return_value=object())  # type: ignore[method-assign]
    monkeypatch.setattr(
        "ocp_module_statistics.application.import_service.validate_and_map",
        lambda _dataset: (_ for _ in ()).throw(ValueError("late invalid row")),
    )
    settings = SimpleNamespace(
        import_enabled=True,
        import_dataset="flensburg-superset-v1",
        import_retry_count=0,
        provider_base_url="https://example.test",
        provider_dashboard_id="dashboard",
        provider_timeout_seconds=1,
    )
    context = SimpleNamespace(
        settings=SimpleNamespace(require=lambda _type: settings),
        database=SessionContext(),
        http=object(),
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None
        ),
        observability=SimpleNamespace(
            tracer=SimpleNamespace(span=lambda *args, **kwargs: Span()),
            metrics=SimpleNamespace(
                increment=lambda *args, **kwargs: None, observe=lambda *args, **kwargs: None
            ),
        ),
    )
    with pytest.raises(ValueError, match="late invalid row"):
        await service.run(context)
    repository.written.assert_not_awaited()
    repository.failed.assert_awaited_once()
