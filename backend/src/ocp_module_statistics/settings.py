"""Validated, module-owned configuration for Statistics imports."""

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class StatisticsSettings(BaseModel):
    """Fail-closed settings loaded through the Host module settings registry."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    provider_base_url: AnyHttpUrl
    provider_dashboard_id: str = Field(
        default="3b53ff0b-6e8c-435e-83f6-666f8a7cc158",
        min_length=1,
        max_length=120,
    )
    provider_timeout_seconds: float = Field(default=30, ge=1, le=300)
    import_enabled: bool = True
    import_retry_count: int = Field(default=2, ge=0, le=5)
    import_dataset: str = Field(default="flensburg-superset-v1", pattern=r"^[a-z0-9-]+$")
    import_schedule_seconds: int | None = Field(default=None, ge=60)

    @field_validator("provider_base_url")
    @classmethod
    def provider_url_is_a_safe_origin(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if (
            value.username
            or value.password
            or value.query
            or value.fragment
            or value.path not in {None, "/"}
        ):
            raise ValueError(
                "provider_base_url must be an origin without credentials, path, query, or fragment"
            )
        return value
