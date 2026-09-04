"""Strict mapping from provider rows to canonical Statistics write models."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ocp_module_statistics.provider import DATASET_SPECS, ProviderDataset

SOURCE = "FLENSBURG_STATISTICS"
DASHBOARD_PATH = "superset/dashboard/3b53ff0b-6e8c-435e-83f6-666f8a7cc158/"
LICENSE = "Datenlizenz Deutschland – Zero – Version 2.0"
AREA_MAPPING = {
    "00": ("Flensburg", "MUNICIPALITY"),
    "01": ("Altstadt", "DISTRICT"),
    "02": ("Neustadt", "DISTRICT"),
    "03": ("Nordstadt", "DISTRICT"),
    "04": ("Westliche Höhe", "DISTRICT"),
    "05": ("Friesischer Berg", "DISTRICT"),
    "06": ("Weiche", "DISTRICT"),
    "07": ("Südstadt", "DISTRICT"),
    "08": ("Sandberg", "DISTRICT"),
    "09": ("Jürgensby", "DISTRICT"),
    "10": ("Fruerlund", "DISTRICT"),
    "11": ("Mürwik", "DISTRICT"),
    "12": ("Engelsby", "DISTRICT"),
    "13": ("Tarup", "DISTRICT"),
}


class ImportValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    key: str
    name: str
    category: str
    dataset_id: int
    unit: str = "persons"
    description: str | None = None


METRICS = (
    MetricDefinition("population", "Bevölkerung", "Bevölkerung", 6),
    MetricDefinition("population_non_german", "Bevölkerung nicht deutsch", "Bevölkerung", 6),
    MetricDefinition("population_age_0_17", "Bevölkerung unter 18", "Altersstruktur", 6),
    MetricDefinition("population_age_18_64", "Bevölkerung 18 bis unter 65", "Altersstruktur", 6),
    MetricDefinition("population_age_65_plus", "Bevölkerung 65 plus", "Altersstruktur", 6),
    MetricDefinition("population_marital_single", "Ledig", "Familienstand", 6),
    MetricDefinition("population_marital_married", "Verheiratet", "Familienstand", 6),
    MetricDefinition("population_marital_divorced", "Geschieden", "Familienstand", 6),
    MetricDefinition("population_marital_widowed", "Verwitwet", "Familienstand", 6),
    MetricDefinition("population_marital_other", "Sonstiger Familienstand", "Familienstand", 6),
    MetricDefinition("population_marital_unknown", "Familienstand ohne Angabe", "Familienstand", 6),
    MetricDefinition("households", "Haushalte", "Haushalte", 7, "households"),
    MetricDefinition(
        "households_non_german", "Haushalte nicht deutsch", "Haushalte", 8, "households"
    ),
    *(
        MetricDefinition(
            f"households_size_{key}", f"Haushalte mit {label}", "Haushaltsgröße", 7, "households"
        )
        for key, label in (
            ("1", "einer Person"),
            ("2", "zwei Personen"),
            ("3", "drei Personen"),
            ("4", "vier Personen"),
            ("5_plus", "fünf oder mehr Personen"),
        )
    ),
    *(
        MetricDefinition(
            f"households_children_{key}",
            f"Haushalte mit {label}",
            "Kinder im Haushalt",
            9,
            "households",
        )
        for key, label in (
            ("1", "einem Kind"),
            ("2", "zwei Kindern"),
            ("3", "drei Kindern"),
            ("4_plus", "vier oder mehr Kindern"),
        )
    ),
)

AGE_KEYS = {
    "0 bis unter 18": "population_age_0_17",
    "18 bis unter 65": "population_age_18_64",
    "65 und älter": "population_age_65_plus",
}
MARITAL_KEYS = {
    "ledig": "population_marital_single",
    "verheiratet": "population_marital_married",
    "geschieden": "population_marital_divorced",
    "verwitwet": "population_marital_widowed",
    "sonstige": "population_marital_other",
    "ohne Angabe": "population_marital_unknown",
}
SUPPRESSED_VALUES = {"", "-", ".", "k.a.", "k.A.", "keine Angabe"}


@dataclass(frozen=True, slots=True)
class CanonicalObservation:
    metric_key: str
    external_area_id: str
    area_name: str
    period_start: date
    period_end: date
    value: Decimal | None
    source_row_hash: str
    is_calculated: bool


@dataclass(frozen=True, slots=True)
class CanonicalImport:
    source_updated_at: datetime
    observations: tuple[CanonicalObservation, ...]
    rows_downloaded: int
    checksum: str
    schema_hash: str
    column_names: str


def parse_value(value: str) -> Decimal | None:
    cleaned = value.strip()
    if cleaned in SUPPRESSED_VALUES:
        return None
    cleaned = cleaned.replace("\u00a0", "").replace(" ", "").removesuffix("%")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ImportValidationError("Invalid numeric value") from exc
    if not parsed.is_finite():
        raise ImportValidationError("Non-finite numeric value")
    return parsed


def validate_and_map(dataset: ProviderDataset) -> CanonicalImport:
    values: dict[tuple[str, str, int], list[Decimal | None]] = defaultdict(list)
    source_names: set[str] = set()
    external_ids = {name: external_id for external_id, (name, _level) in AREA_MAPPING.items()}
    metric_columns = {spec.id: spec.metric_column for spec in DATASET_SPECS}
    seen_rows: set[tuple[int, tuple[tuple[str, str], ...]]] = set()
    for dataset_id, rows in dataset.rows.items():
        if dataset_id not in metric_columns:
            raise ImportValidationError("Unsupported dataset identity")
        for row in rows:
            identity = (dataset_id, tuple(sorted(row.items())))
            if identity in seen_rows:
                raise ImportValidationError("Duplicate provider row")
            seen_rows.add(identity)
            area_name = row.get("Stadtteilname", "").strip()
            if not area_name:
                if dataset_id == 10:
                    continue
                raise ImportValidationError("Missing area identity")
            source_names.add(area_name)
            try:
                period = date.fromisoformat(row["Time"][:10])
                value = parse_value(row[metric_columns[dataset_id]])
            except (KeyError, ValueError) as exc:
                if isinstance(exc, ImportValidationError):
                    raise
                raise ImportValidationError("Invalid period or required field") from exc
            for metric_key in _row_metrics(dataset_id, row):
                values[(metric_key, area_name, period.year)].append(value)

    expected = {name for name, level in AREA_MAPPING.values() if level == "DISTRICT"}
    unknown = sorted(source_names - expected)
    missing = sorted(expected - source_names)
    if unknown or missing:
        raise ImportValidationError(f"Area mapping failed: unknown={unknown}, missing={missing}")

    aggregated = {
        key: None if any(part is None for part in parts) else sum(parts, Decimal(0))
        for key, parts in values.items()
    }
    for metric_key, year in {(key[0], key[2]) for key in aggregated}:
        parts = [
            aggregated[(metric_key, name, year)]
            for name in expected
            if (metric_key, name, year) in aggregated
        ]
        if len(parts) != len(expected):
            raise ImportValidationError(f"Incomplete area coverage for {metric_key}/{year}")
        aggregated[(metric_key, "Flensburg", year)] = (
            None if any(part is None for part in parts) else sum(parts, Decimal(0))
        )

    known_metrics = {metric.key for metric in METRICS}
    observations = []
    for (metric_key, area_name, year), value in sorted(aggregated.items()):
        if metric_key not in known_metrics or area_name not in external_ids:
            raise ImportValidationError("Unknown metric or area mapping")
        area_id = external_ids[area_name]
        source_hash = _source_hash(metric_key, area_id, year, value)
        observations.append(
            CanonicalObservation(
                metric_key=metric_key,
                external_area_id=area_id,
                area_name=area_name,
                period_start=date(year, 1, 1),
                period_end=date(year, 12, 31),
                value=value,
                source_row_hash=source_hash,
                is_calculated=area_name == "Flensburg",
            )
        )
    column_names = {str(key): list(value) for key, value in dataset.column_names.items()}
    return CanonicalImport(
        source_updated_at=dataset.source_updated_at,
        observations=tuple(observations),
        rows_downloaded=sum(len(rows) for rows in dataset.rows.values()),
        checksum=hashlib.sha256(b"\0".join(dataset.raw_parts)).hexdigest(),
        schema_hash=hashlib.sha256(json.dumps(column_names, sort_keys=True).encode()).hexdigest(),
        column_names=json.dumps(column_names, ensure_ascii=False, sort_keys=True),
    )


def _row_metrics(dataset_id: int, row: dict[str, str]) -> tuple[str, ...]:
    if row.get("Wohnstatus") != "Hauptwohnung":
        return ()
    if dataset_id == 6:
        try:
            keys = ["population", AGE_KEYS[row["Altersgruppe"]], MARITAL_KEYS[row["Familienstand"]]]
        except KeyError as exc:
            raise ImportValidationError("Unknown statistical dimension") from exc
        if row["Migrationshintergrund"] == "Nicht deutsch":
            keys.append("population_non_german")
        return tuple(keys)
    if dataset_id == 7:
        size = row["ZahlPersonenHaushalt"].replace("+", "_plus")
        key = f"households_size_{size}"
        if key not in {metric.key for metric in METRICS}:
            raise ImportValidationError("Unknown household size")
        return "households", key
    if dataset_id == 8:
        return (
            ("households_non_german",)
            if row["Migrationshintergrund_Haushalte"] == "Nicht deutsch"
            else ()
        )
    if dataset_id == 9 and row["ZahlKinderHaushalt"]:
        key = f"households_children_{row['ZahlKinderHaushalt'].replace('+', '_plus')}"
        if key not in {metric.key for metric in METRICS}:
            raise ImportValidationError("Unknown household children dimension")
        return (key,)
    return ()


def _source_hash(metric_key: str, source_area_id: str, year: int, value: Decimal | None) -> str:
    canonical = json.dumps(
        [metric_key, source_area_id, year, str(value) if value is not None else None],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
