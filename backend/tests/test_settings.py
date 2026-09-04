import pytest
from pydantic import ValidationError

from ocp_module_statistics.settings import StatisticsSettings


def test_valid_settings_and_safe_defaults() -> None:
    settings = StatisticsSettings(provider_base_url="https://statistics.example.test")
    assert settings.import_enabled is True
    assert settings.import_retry_count == 2
    assert settings.provider_timeout_seconds == 30


@pytest.mark.parametrize(
    "values",
    [
        {},
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
