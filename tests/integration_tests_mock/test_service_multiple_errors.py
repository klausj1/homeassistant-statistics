"""Mock integration tests for service responses containing multiple validation errors."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import ServiceCall

from custom_components.import_statistics import async_setup
from custom_components.import_statistics.const import ATTR_DECIMAL, ATTR_DELIMITER, ATTR_FILENAME, ATTR_TIMEZONE_IDENTIFIER
from tests.conftest import create_mock_states_with_unit, get_service_handler, mock_async_add_executor_job


@pytest.mark.asyncio
@pytest.mark.parametrize("import_type", ["file", "json"])
async def test_import_returns_all_errors_without_writing(import_type: str) -> None:
    """File and JSON imports return all row validation errors without database writes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hass = MagicMock()
        hass.config.config_dir = tmpdir
        hass.config.time_zone = "UTC"
        hass.async_add_executor_job = mock_async_add_executor_job
        hass.states = create_mock_states_with_unit("kWh")
        await async_setup(hass, {})

        if import_type == "file":
            test_file = Path(tmpdir) / "invalid.csv"
            await hass.async_add_executor_job(
                lambda: test_file.write_text(
                    "statistic_id\tstart\tunit\tsum\tstate\n"
                    "counter.energy\t01.01.2022 00:30\tkWh\tbad\t100.0\n"
                    "counter.energy\t01.01.2022 01:15\tkWh\tinvalid\t110.0\n",
                    encoding="utf-8",
                )
            )
            service_name = "import_from_file"
            call_data = {
                ATTR_FILENAME: "invalid.csv",
                ATTR_TIMEZONE_IDENTIFIER: "UTC",
                ATTR_DELIMITER: "\t",
                ATTR_DECIMAL: "dot ('.')",
            }
        else:
            service_name = "import_from_json"
            call_data = {
                ATTR_TIMEZONE_IDENTIFIER: "UTC",
                ATTR_DECIMAL: "dot ('.')",
                "entities": [
                    {
                        "id": "counter.energy",
                        "unit": "kWh",
                        "values": [
                            {"datetime": "01.01.2022 00:30", "sum": 100.0, "state": 100.0},
                            {"datetime": "01.01.2022 01:15", "sum": 110.0, "state": 110.0},
                        ],
                    }
                ],
            }

        call = ServiceCall(hass, "import_statistics", service_name, call_data)
        handler = get_service_handler(hass, service_name)
        with (
            patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
            patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_add,
        ):
            response = await handler(call)

        assert response["failed"] is True
        if import_type == "file":
            assert len(response["errors"]) == 4
            assert any("Invalid timestamp" in error for error in response["errors"])
            assert any("Invalid float value" in error for error in response["errors"])
        else:
            assert len(response["errors"]) == 2
            assert all("Invalid timestamp" in error for error in response["errors"])
        mock_import.assert_not_called()
        mock_add.assert_not_called()


@pytest.mark.asyncio
async def test_export_returns_all_time_errors() -> None:
    """Invalid start and end times are both returned in the export response."""
    hass = MagicMock()
    hass.config.time_zone = "UTC"
    await async_setup(hass, {})
    call = ServiceCall(
        hass,
        "import_statistics",
        "export_statistics",
        {
            ATTR_FILENAME: "export.tsv",
            ATTR_TIMEZONE_IDENTIFIER: "UTC",
            "start_time": "invalid start",
            "end_time": "invalid end",
        },
    )
    handler = get_service_handler(hass, "export_statistics")

    response = await handler(call)

    assert response["failed"] is True
    assert len(response["errors"]) == 2
    assert all("Invalid datetime format" in error for error in response["errors"])
