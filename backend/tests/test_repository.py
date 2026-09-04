from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ocp_module_statistics.persistence.repository import StatisticsRepository
from ocp_module_statistics.validation import AREA_MAPPING, CanonicalImport, CanonicalObservation


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def mappings(self):
        return self

    def all(self):
        return self.rows


class StateSession:
    def __init__(self):
        self.runs = 0
        self.mappings = {}
        self.metrics = {}
        self.observations = {}
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, statement, parameters):
        sql = str(statement).lower()
        if "insert into statistical_import_runs" in sql:
            self.runs += 1
            return self.runs
        if "insert into external_area_mappings" in sql:
            mapping_id = len(self.mappings) + 1
            self.mappings[parameters["external_id"]] = {
                "id": mapping_id,
                "external_area_id": parameters["external_id"],
                "external_area_name": parameters["name"],
                "level": parameters["level"],
            }
            return mapping_id
        if "insert into statistical_datasets" in sql:
            return 100 + int(parameters["external_id"])
        if "insert into statistical_metrics" in sql:
            metric_id = self.metrics.setdefault(parameters["key"], len(self.metrics) + 1000)
            return metric_id
        raise AssertionError(sql)

    async def execute(self, statement, parameters):
        sql = str(statement).lower()
        if "select id,external_area_id" in sql:
            return Result(self.mappings.values())
        if "select metric_id,statistical_area_id" in sql:
            return Result(
                {
                    "metric_id": key[0],
                    "statistical_area_id": key[1],
                    "period_start": key[2],
                    "source_area_id": key[3],
                    "source_row_hash": value,
                }
                for key, value in self.observations.items()
            )
        if "insert into statistical_observations" in sql:
            key = (
                parameters["metric_id"],
                parameters["statistical_area_id"],
                parameters["period_start"],
                parameters["source_area_id"],
            )
            self.observations[key] = parameters["source_row_hash"]
        return Result()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def canonical(value=Decimal(42), source_hash="first"):
    return CanonicalImport(
        source_updated_at=datetime(2026, 8, 6, tzinfo=UTC),
        observations=(
            CanonicalObservation(
                metric_key="population",
                external_area_id="01",
                area_name="Altstadt",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
                value=value,
                source_row_hash=source_hash,
                is_calculated=False,
            ),
        ),
        rows_downloaded=1,
        checksum="checksum",
        schema_hash="schema",
        column_names="[]",
    )


@pytest.mark.asyncio
async def test_import_is_idempotent_and_changed_value_updates() -> None:
    repository = StatisticsRepository()
    session = StateSession()
    first = await repository.write_import(session, 1, canonical(), "https://example.test/source")
    second = await repository.write_import(session, 2, canonical(), "https://example.test/source")
    changed = await repository.write_import(
        session, 3, canonical(Decimal(43), "changed"), "https://example.test/source"
    )
    assert (first.inserted, first.updated, first.unchanged) == (1, 0, 0)
    assert (second.inserted, second.updated, second.unchanged) == (0, 0, 1)
    assert (changed.inserted, changed.updated, changed.unchanged) == (0, 1, 0)
    assert len(session.observations) == 1


@pytest.mark.asyncio
async def test_ambiguous_stored_mapping_fails_before_observation_write() -> None:
    session = StateSession()
    for index, (external_id, (name, level)) in enumerate(AREA_MAPPING.items(), start=1):
        session.mappings[external_id] = {
            "id": index,
            "external_area_id": external_id,
            "external_area_name": name,
            "level": level,
        }
    session.mappings["duplicate"] = {
        "id": 99,
        "external_area_id": "duplicate",
        "external_area_name": "Altstadt",
        "level": "DISTRICT",
    }
    with pytest.raises(ValueError, match="Ambiguous"):
        await StatisticsRepository().write_import(
            session, 1, canonical(), "https://example.test/source"
        )
    assert session.observations == {}


@pytest.mark.asyncio
async def test_failed_run_rolls_back_writes_before_audit_update() -> None:
    session = StateSession()
    await StatisticsRepository().fail_run(session, 1, ValueError("late validation failure"))
    assert session.rollbacks == 1
    assert session.commits == 1
