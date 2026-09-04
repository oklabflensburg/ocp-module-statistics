from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from app.platform.modules.sdk import StatisticsArea, StatisticsSelection

from ocp_module_statistics.application.query_service import SqlStatisticsQueryService


class MappingResult:
    def __init__(self, *, first=None, all_rows=()) -> None:
        self._first = first
        self._all = all_rows

    def mappings(self):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._all


def selection(*, inherited: bool = False, target_type: str = "DISTRICT"):
    municipality = StatisticsArea(
        UUID("00000000-0000-0000-0000-000000000001"),
        "flensburg",
        "Flensburg",
        "MUNICIPALITY",
    )
    target = StatisticsArea(
        UUID("00000000-0000-0000-0000-000000000002"),
        "nordstadt",
        "Nordstadt",
        target_type,
    )
    requested = (
        StatisticsArea(
            UUID("00000000-0000-0000-0000-000000000003"),
            "hafen",
            "Hafen",
            "QUARTER",
        )
        if inherited
        else target
    )
    return StatisticsSelection(requested, target, municipality, inherited)


@pytest.mark.asyncio
async def test_missing_mapping_returns_none_after_one_read() -> None:
    session = SimpleNamespace(execute=AsyncMock(return_value=MappingResult()))
    assert await SqlStatisticsQueryService().for_selection(session, selection()) is None
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_district_latest_values_include_municipality_comparison_and_source() -> None:
    imported = datetime(2026, 8, 1, tzinfo=UTC)
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                MappingResult(first={"target_id": 2, "municipality_id": 1, "source": "sh"}),
                MappingResult(
                    all_rows=(
                        {
                            "key": "population",
                            "name": "Bevölkerung",
                            "category": "Demografie",
                            "unit": "Personen",
                            "value_numeric": Decimal(80),
                            "period_start": date(2025, 1, 1),
                            "is_calculated": False,
                            "municipality_value": Decimal(100),
                        },
                    )
                ),
                MappingResult(
                    first={
                        "name": "Statistik Nord",
                        "source_url": "https://example.invalid/data",
                        "license": "CC BY 4.0",
                        "last_import_at": imported,
                        "source_updated_at": None,
                    }
                ),
            ]
        )
    )
    result = await SqlStatisticsQueryService().for_selection(session, selection())
    assert result is not None
    assert result.statistics_area.name == "Nordstadt"
    assert result.inherited_from_parent is False
    assert result.source is not None and result.source.name == "Statistik Nord"
    value = result.latest[0]
    assert value.difference == Decimal(-20)
    assert value.relative_difference == Decimal(-20)
    assert value.area_level == "DISTRICT"


@pytest.mark.asyncio
async def test_municipality_selection_compares_with_itself() -> None:
    selected = selection(target_type="MUNICIPALITY")
    selected = StatisticsSelection(
        selected.municipality, selected.municipality, selected.municipality
    )
    row = {
        "key": "population",
        "name": "Bevölkerung",
        "category": "Demografie",
        "unit": "Personen",
        "value_numeric": Decimal(100),
        "period_start": date(2025, 1, 1),
        "is_calculated": False,
        "municipality_value": Decimal(100),
    }
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                MappingResult(first={"target_id": 1, "municipality_id": 1, "source": "sh"}),
                MappingResult(all_rows=(row,)),
                MappingResult(),
            ]
        )
    )
    result = await SqlStatisticsQueryService().for_selection(session, selected)
    assert result is not None
    assert result.latest[0].difference == Decimal(0)
    assert result.latest[0].relative_difference == Decimal(0)


@pytest.mark.asyncio
async def test_inherited_selection_is_preserved_without_quarter_policy() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                MappingResult(first={"target_id": 2, "municipality_id": 1, "source": "sh"}),
                MappingResult(all_rows=()),
                MappingResult(),
            ]
        )
    )
    result = await SqlStatisticsQueryService().for_selection(session, selection(inherited=True))
    assert result is not None
    assert result.area.area_type == "QUARTER"
    assert result.statistics_area.area_type == "DISTRICT"
    assert result.inherited_from_parent is True


@pytest.mark.asyncio
async def test_series_and_missing_metric() -> None:
    mapping = {"target_id": 2, "municipality_id": 1, "source": "sh"}
    metric = {
        "id": 7,
        "key": "population",
        "name": "Bevölkerung",
        "unit": "Personen",
        "category": "Demografie",
    }
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                MappingResult(first=mapping),
                MappingResult(first=metric),
                MappingResult(
                    all_rows=(
                        {
                            "period_start": date(2024, 1, 1),
                            "value_numeric": Decimal(79),
                            "value_text": None,
                        },
                        {
                            "period_start": date(2025, 1, 1),
                            "value_numeric": None,
                            "value_text": "suppressed",
                        },
                    )
                ),
                MappingResult(),
            ]
        )
    )
    result = await SqlStatisticsQueryService().series_for_selection(
        session, selection(), "population"
    )
    assert result is not None
    assert result.metric["key"] == "population"
    assert [point.period for point in result.series] == ["2024", "2025"]
    assert result.series[1].suppressed is True

    missing_session = SimpleNamespace(
        execute=AsyncMock(side_effect=[MappingResult(first=mapping), MappingResult()])
    )
    assert (
        await SqlStatisticsQueryService().series_for_selection(
            missing_session, selection(), "missing"
        )
        is None
    )


def test_service_exposes_no_transaction_ownership_methods() -> None:
    service = SqlStatisticsQueryService()
    assert not any(hasattr(service, name) for name in ("commit", "rollback", "flush"))
