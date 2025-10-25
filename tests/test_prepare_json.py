"""Unit tests for prepare_json_* functions."""

from homeassistant.core import ServiceCall

from custom_components.import_statistics import prepare_data

test_timezone = "America/Los_Angeles"
test_data = {
    "timezone_identifier": test_timezone,
    "entities": [
        {
            "id": "sensor.finance_test",
            "unit": "$",
            "values": [
                {"state": 10.0, "sum": 10.0, "datetime": "13.09.2024 00:00"},
                {"state": 20.0, "sum": 20.0, "datetime": "14.09.2024 00:00"},
                {"state": 10.0, "sum": 10.0, "datetime": "15.09.2024 00:00"},
            ],
        }
    ],
}


def test_prepare_json_entities() -> None:
    """Test prepare_json_entities function."""
    call = ServiceCall("domain_name", "service_name", test_data, test_data)
    timezone, entities = prepare_data.prepare_json_entities(call)
    assert timezone.key == test_timezone
    assert len(entities) == 1
