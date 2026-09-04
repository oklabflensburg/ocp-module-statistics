import pytest
from pydantic import ValidationError

from ocp_module_statistics.settings import StatisticsSettings


def test_query_only_defaults_need_no_provider_configuration() -> None:
    settings = StatisticsSettings()
    assert settings.import_enabled is False
    assert settings.provider_base_url is None
    assert settings.import_retry_count == 2
    assert settings.provider_timeout_seconds == 30


def test_enabled_import_requires_provider_url() -> None:
    with pytest.raises(ValidationError, match="provider_base_url is required"):
        StatisticsSettings(import_enabled=True)


def test_enabled_import_accepts_valid_provider_url() -> None:
    settings = StatisticsSettings(
        import_enabled=True,
        provider_base_url="https://statistics.example.test",
    )
    assert settings.import_enabled is True
    assert settings.provider_base_url is not None


@pytest.mark.parametrize("provider_base_url", [None, "https://statistics.example.test"])
def test_disabled_import_allows_optional_provider_url(provider_base_url) -> None:
    settings = StatisticsSettings(provider_base_url=provider_base_url)
    assert settings.import_enabled is False


@pytest.mark.parametrize(
    "values",
    [
        {"provider_base_url": "not-a-url"},
        {"provider_base_url": "https://example.test", "provider_timeout_seconds": 0},
        {"provider_base_url": "https://example.test", "import_retry_count": 9},
        {"provider_base_url": "https://user:secret@example.test"},
    ],
)
def test_invalid_or_missing_settings_fail_closed_without_echoing_secrets(values) -> None:
    with pytest.raises(ValidationError) as caught:
        StatisticsSettings.model_validate(values)
    assert "secret" not in str(caught.value)
