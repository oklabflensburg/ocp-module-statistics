from datetime import UTC, datetime

import pytest

from ocp_module_statistics.provider import ProviderDataset
from ocp_module_statistics.validation import (
    AREA_MAPPING,
    ImportValidationError,
    parse_value,
    validate_and_map,
)


def dataset(rows):
    return ProviderDataset(
        datetime(2026, 8, 6, tzinfo=UTC),
        {6: tuple(rows)},
        (b"source",),
        {
            6: (
                "Time",
                "Wohnstatus",
                "Migrationshintergrund",
                "Altersgruppe",
                "Familienstand",
                "Stadtteilname",
                "Anzahl",
            )
        },
    )


def valid_rows():
    return [
        {
            "Time": "2025-01-01",
            "Wohnstatus": "Hauptwohnung",
            "Migrationshintergrund": "Nicht deutsch",
            "Altersgruppe": "0 bis unter 18",
            "Familienstand": "ledig",
            "Stadtteilname": name,
            "Anzahl": str(index),
        }
        for index, (name, level) in enumerate(AREA_MAPPING.values(), start=1)
        if level == "DISTRICT"
    ]


def test_validation_maps_rows_and_calculates_municipality() -> None:
    result = validate_and_map(dataset(valid_rows()))
    assert result.rows_downloaded == 13
    assert any(row.area_name == "Flensburg" and row.is_calculated for row in result.observations)
    population = [row for row in result.observations if row.metric_key == "population"]
    assert len(population) == 14
    assert population[-1].value is not None


@pytest.mark.parametrize("value", ["garbage", "NaN", "Infinity"])
def test_invalid_numeric_values_fail_closed(value) -> None:
    with pytest.raises(ImportValidationError):
        parse_value(value)


def test_duplicate_observation_source_row_fails_closed() -> None:
    rows = valid_rows()
    rows.append(dict(rows[0]))
    with pytest.raises(ImportValidationError, match="Duplicate"):
        validate_and_map(dataset(rows))


def test_unknown_area_fails_closed() -> None:
    rows = valid_rows()
    rows[0]["Stadtteilname"] = "Unknown"
    with pytest.raises(ImportValidationError, match="Area mapping"):
        validate_and_map(dataset(rows))


def test_late_validation_failure_produces_no_canonical_partial_result() -> None:
    rows = valid_rows()
    rows[-1]["Anzahl"] = "invalid"
    with pytest.raises(ImportValidationError):
        validate_and_map(dataset(rows))
