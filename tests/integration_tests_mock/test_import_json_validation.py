"""Integration tests for JSON import validation (mocked HA)."""

import tempfile
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import async_setup
from custom_components.import_statistics.const import ATTR_DECIMAL, ATTR_TIMEZONE_IDENTIFIER
from tests.conftest import create_mock_recorder_instance, create_mock_states_with_unit, get_service_handler, mock_async_add_executor_job


@pytest.mark.asyncio
async def test_import_json_valid_calls_import() -> None:
    """Valid JSON import should call async_import_statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = tmpdir
        hass.async_add_executor_job = mock_async_add_executor_job
        hass.states = create_mock_states_with_unit("kWh")

        await async_setup(hass, {})
        json_handler = get_service_handler(hass, "import_from_json")

        call = ServiceCall(
            hass,
            "import_statistics",
            "import_from_json",
            {
                ATTR_TIMEZONE_IDENTIFIER: "UTC",
                ATTR_DECIMAL: "dot ('.')",
                "entities": [
                    {
                        "id": "counter.energy",
                        "unit": "kWh",
                        "values": [
                            {"datetime": "01.01.2022 00:00", "sum": 100.0, "state": 100.0},
                        ],
                    }
                ],
            },
        )

        with (
            patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
            patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
        ):
            await json_handler(call)
            assert mock_import.called


@pytest.mark.asyncio
async def test_import_json_invalid_raises_error() -> None:
    """Invalid JSON import payload should raise HomeAssistantError with helpful message."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = tmpdir
        hass.async_add_executor_job = mock_async_add_executor_job
        hass.states = create_mock_states_with_unit("kWh")

        await async_setup(hass, {})
        json_handler = get_service_handler(hass, "import_from_json")

        # Malformed payload: missing 'entities' key
        call = ServiceCall(
            hass,
            "import_statistics",
            "import_from_json",
            {ATTR_TIMEZONE_IDENTIFIER: "UTC", ATTR_DECIMAL: "dot ('.')", "not_entities": []},
        )

        with pytest.raises(HomeAssistantError, match="Invalid JSON import format"):
            await json_handler(call)
