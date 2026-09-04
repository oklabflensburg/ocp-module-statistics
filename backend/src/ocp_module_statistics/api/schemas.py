"""Stable HTTP DTOs for Statistics-owned catalog and import data."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StatisticsSourceDto(BaseModel):
    source: str
    dataset: str
    name: str
    description: str | None = None
    source_url: str
    license: str
    update_frequency: str
    last_import_at: datetime | None = None
    source_updated_at: datetime | None = None

    model_config = ConfigDict(frozen=True)


class StatisticsMetricDto(BaseModel):
    key: str
    name: str
    description: str | None = None
    category: str
    unit: str
    value_type: str
    aggregation_method: str | None = None
    source: str
    dataset: str
    dataset_name: str
    public: bool = True

    model_config = ConfigDict(frozen=True)


class StatisticsMetricPageDto(BaseModel):
    items: list[StatisticsMetricDto]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)

    model_config = ConfigDict(frozen=True)


class StatisticsImportRunDto(BaseModel):
    id: int
    source: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    rows_downloaded: int = Field(ge=0)
    rows_imported: int = Field(ge=0)
    rows_updated: int = Field(ge=0)
    rows_unchanged: int = Field(ge=0)
    rows_rejected: int = Field(ge=0)
    error_summary: str | None = None

    model_config = ConfigDict(frozen=True)


class StatisticsImportRunPageDto(BaseModel):
    items: list[StatisticsImportRunDto]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)

    model_config = ConfigDict(frozen=True)


class StatisticsImportStatusDto(BaseModel):
    import_enabled: bool
    job_available: bool
    last_run: StatisticsImportRunDto | None = None

    model_config = ConfigDict(frozen=True)
