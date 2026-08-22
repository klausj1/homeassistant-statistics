"""Unit tests for JSON import validation."""

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import helpers


def test_validate_json_schema_valid() -> None:
    """Valid payload should pass JSON schema validation."""
    payload = {
        "entities": [
            {
                "id": "sensor.test_counter",
                "unit": "kWh",
                "values": [{"datetime": "17.03.2024 02:00", "sum": 12.34}],
            }
        ]
    }

    # Should not raise
    helpers.validate_json_schema(payload)


def test_validate_json_schema_missing_entities() -> None:
    """Missing 'entities' key should raise HomeAssistantError with example."""
    payload = {"not_entities": []}

    with pytest.raises(HomeAssistantError) as exc:
        helpers.validate_json_schema(payload)

    assert "Invalid JSON import format" in str(exc.value)
    assert "Example of valid payload" in str(exc.value)


def test_validate_json_schema_entity_missing_id() -> None:
    """Entity missing 'id' should raise HomeAssistantError."""
    payload = {"entities": [{"unit": "kWh", "values": [{"datetime": "17.03.2024 02:00", "sum": 1}]}]}

    with pytest.raises(HomeAssistantError) as exc:
        helpers.validate_json_schema(payload)

    assert "Invalid JSON import format" in str(exc.value)
