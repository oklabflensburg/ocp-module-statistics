"""Read ownership metadata for the existing unqualified statistics tables."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)

METADATA = MetaData()

Table(
    "statistical_datasets",
    METADATA,
    Column("id", Integer, primary_key=True),
    Column("source", String(40), nullable=False),
    Column("external_dataset_id", String(80), nullable=False),
    Column("name", String(200), nullable=False),
    Column("description", Text),
    Column("source_url", Text, nullable=False),
    Column("license", String(160), nullable=False),
    Column("update_frequency", String(40), nullable=False),
    Column("last_import_at", DateTime(timezone=True)),
    Column("source_updated_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

Table(
    "statistical_metrics",
    METADATA,
    Column("id", Integer, primary_key=True),
    Column("dataset_id", ForeignKey("statistical_datasets.id"), nullable=False),
    Column("key", String(120), nullable=False),
    Column("name", String(200), nullable=False),
    Column("description", Text),
    Column("unit", String(40), nullable=False),
    Column("value_type", String(24), nullable=False),
    Column("category", String(80), nullable=False),
    Column("aggregation_method", String(40)),
    Column("public", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

Table(
    "external_area_mappings",
    METADATA,
    Column("id", Integer, primary_key=True),
    Column("source", String(40), nullable=False),
    Column("external_area_id", String(80), nullable=False),
    Column("external_area_name", String(200), nullable=False),
    Column("level", String(40), nullable=False),
    Column("valid_from", Date),
    Column("valid_to", Date),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

Table(
    "statistical_observations",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("metric_id", ForeignKey("statistical_metrics.id"), nullable=False),
    Column("statistical_area_id", ForeignKey("external_area_mappings.id"), nullable=False),
    Column("period_type", String(24), nullable=False),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("value_numeric", Numeric(20, 4)),
    Column("value_text", Text),
    Column("source_area_id", String(80), nullable=False),
    Column("source_row_hash", String(64), nullable=False),
    Column("is_calculated", Boolean, nullable=False),
    Column("imported_at", DateTime(timezone=True)),
    Column("source_updated_at", DateTime(timezone=True)),
)

Table(
    "statistical_import_runs",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("source", String(40), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", String(24), nullable=False),
    Column("rows_downloaded", Integer, nullable=False),
    Column("rows_imported", Integer, nullable=False),
    Column("rows_updated", Integer, nullable=False),
    Column("rows_unchanged", Integer, nullable=False),
    Column("rows_rejected", Integer, nullable=False),
    Column("error_message", Text),
    Column("source_url", Text, nullable=False),
    Column("checksum", String(64)),
    Column("schema_hash", String(64)),
    Column("column_names", Text),
)

ADOPTED_TABLES = frozenset(METADATA.tables)
