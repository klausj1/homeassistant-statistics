"""Test importing statistics with empty units."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import async_setup
from custom_components.import_statistics.const import (
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_FILENAME,
    ATTR_TIMEZONE_IDENTIFIER,
)
from tests.conftest import create_mock_recorder_instance, get_service_handler, mock_async_add_executor_job


class TestImportEmptyUnits:
    """Test importing statistics with empty units."""

    @pytest.mark.asyncio
    async def test_import_empty_unit_matches_database_empty(self) -> None:
        """Test importing with empty unit when database also has empty unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            await async_setup(hass, {})
            import_handler = get_service_handler(hass, "import_from_file")

            # Create test file with empty unit (empty cell)
            test_file = Path(tmpdir) / "empty_unit.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tmean\tmin\tmax\n"
                "sensor.dimensionless\t01.01.2022 00:00\t\t20.5\t18.2\t22.8\n"
                "sensor.dimensionless\t01.01.2022 01:00\t\t21.3\t19.1\t23.5\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "empty_unit.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            # Mock recorder with empty unit in database
            mock_recorder = create_mock_recorder_instance()
            mock_metadata = {
                "sensor.dimensionless": (
                    1,
                    {
                        "statistic_id": "sensor.dimensionless",
                        "unit_of_measurement": None,  # Database has no unit
                        "has_mean": True,
                        "has_sum": False,
                    },
                )
            }

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.import_service.get_metadata", return_value=mock_metadata),
            ):
                # Should succeed - both empty
                await import_handler(call)

                assert mock_import.called
                metadata = mock_import.call_args[0][1]
                assert metadata["unit_of_measurement"] is None
                assert metadata["statistic_id"] == "sensor.dimensionless"

    @pytest.mark.asyncio
    async def test_import_empty_unit_fails_when_database_has_unit(self) -> None:
        """Test importing with empty unit when database has a unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            await async_setup(hass, {})
            import_handler = get_service_handler(hass, "import_from_file")

            # Create test file with empty unit
            test_file = Path(tmpdir) / "empty_unit.csv"
            test_file.write_text("statistic_id\tstart\tunit\tmean\tmin\tmax\nsensor.temperature\t01.01.2022 00:00\t\t20.5\t18.2\t22.8\n")

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "empty_unit.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            # Mock recorder with unit in database
            mock_recorder = create_mock_recorder_instance()
            mock_metadata = {
                "sensor.temperature": (
                    1,
                    {
                        "statistic_id": "sensor.temperature",
                        "unit_of_measurement": "°C",  # Database has unit
                        "has_mean": True,
                        "has_sum": False,
                    },
                )
            }

            with (
                patch("custom_components.import_statistics.import_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.import_service.get_metadata", return_value=mock_metadata),
                pytest.raises(HomeAssistantError, match=r"Unit mismatch.*\(empty\).*°C"),
            ):
                # Should fail - empty vs °C
                await import_handler(call)

    @pytest.mark.asyncio
    async def test_import_unit_fails_when_database_empty(self) -> None:
        """Test importing with unit when database has empty unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            await async_setup(hass, {})
            import_handler = get_service_handler(hass, "import_from_file")

            # Create test file with unit
            test_file = Path(tmpdir) / "with_unit.csv"
            test_file.write_text("statistic_id\tstart\tunit\tmean\tmin\tmax\nsensor.dimensionless\t01.01.2022 00:00\t°C\t20.5\t18.2\t22.8\n")

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "with_unit.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            # Mock recorder with empty unit in database
            mock_recorder = create_mock_recorder_instance()
            mock_metadata = {
                "sensor.dimensionless": (
                    1,
                    {
                        "statistic_id": "sensor.dimensionless",
                        "unit_of_measurement": None,  # Database has no unit
                        "has_mean": True,
                        "has_sum": False,
                    },
                )
            }

            with (
                patch("custom_components.import_statistics.import_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.import_service.get_metadata", return_value=mock_metadata),
                pytest.raises(HomeAssistantError, match=r"Unit mismatch.*°C.*\(empty\)"),
            ):
                # Should fail - °C vs empty
                await import_handler(call)

    @pytest.mark.asyncio
    async def test_import_new_statistic_with_empty_unit(self) -> None:
        """Test importing new statistic with empty unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            await async_setup(hass, {})
            import_handler = get_service_handler(hass, "import_from_file")

            # Create test file with empty unit for new statistic
            test_file = Path(tmpdir) / "new_empty.csv"
            test_file.write_text("statistic_id\tstart\tunit\tmean\tmin\tmax\nsensor.new_dimensionless\t01.01.2022 00:00\t\t20.5\t18.2\t22.8\n")

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "new_empty.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            # Mock recorder with NO existing metadata (new statistic)
            mock_recorder = create_mock_recorder_instance()
            mock_metadata = {}  # Empty dict = no existing statistics

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.import_service.get_metadata", return_value=mock_metadata),
            ):
                # Should succeed - new statistic with empty unit
                await import_handler(call)

                assert mock_import.called
                metadata = mock_import.call_args[0][1]
                assert metadata["unit_of_measurement"] is None
                assert metadata["statistic_id"] == "sensor.new_dimensionless"

    @pytest.mark.asyncio
    async def test_import_mixed_empty_and_units_in_same_file(self) -> None:
        """Test importing file with some statistics having units and some empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            await async_setup(hass, {})
            import_handler = get_service_handler(hass, "import_from_file")

            # Create test file with mixed units
            test_file = Path(tmpdir) / "mixed.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tmean\tmin\tmax\n"
                "sensor.temperature\t01.01.2022 00:00\t°C\t20.5\t18.2\t22.8\n"
                "sensor.dimensionless\t01.01.2022 00:00\t\t50.0\t45.0\t55.0\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "mixed.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            # Mock recorder with matching metadata
            mock_recorder = create_mock_recorder_instance()
            mock_metadata = {
                "sensor.temperature": (
                    1,
                    {
                        "statistic_id": "sensor.temperature",
                        "unit_of_measurement": "°C",
                        "has_mean": True,
                        "has_sum": False,
                    },
                ),
                "sensor.dimensionless": (
                    2,
                    {
                        "statistic_id": "sensor.dimensionless",
                        "unit_of_measurement": None,
                        "has_mean": True,
                        "has_sum": False,
                    },
                ),
            }

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.import_service.get_metadata", return_value=mock_metadata),
            ):
                # Should succeed - both match their database units
                await import_handler(call)

                assert mock_import.call_count == 2

    @pytest.mark.asyncio
    async def test_import_json_with_empty_unit(self) -> None:
        """Test importing JSON format with empty unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            await async_setup(hass, {})
            json_handler = get_service_handler(hass, "import_from_json")

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_json",
                {
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    "entities": [
                        {
                            "id": "sensor.dimensionless",
                            "unit": "",  # Empty string in JSON
                            "values": [
                                {"datetime": "01.01.2022 00:00", "mean": 20.5, "min": 18.2, "max": 22.8},
                            ],
                        }
                    ],
                },
            )

            # Mock recorder with empty unit in database
            mock_recorder = create_mock_recorder_instance()
            mock_metadata = {
                "sensor.dimensionless": (
                    1,
                    {
                        "statistic_id": "sensor.dimensionless",
                        "unit_of_measurement": None,
                        "has_mean": True,
                        "has_sum": False,
                    },
                )
            }

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=mock_recorder),
                patch("custom_components.import_statistics.import_service.get_metadata", return_value=mock_metadata),
            ):
                # Should succeed - empty string normalized to None
                await json_handler(call)

                assert mock_import.called
                metadata = mock_import.call_args[0][1]
                assert metadata["unit_of_measurement"] is None
