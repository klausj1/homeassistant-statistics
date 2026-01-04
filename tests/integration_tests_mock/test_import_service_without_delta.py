"""Integration tests for standard (non-delta) column import feature."""

import datetime as dt
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import setup
from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_FILENAME,
    ATTR_TIMEZONE_IDENTIFIER,
    ATTR_UNIT_FROM_ENTITY,
)
from custom_components.import_statistics.helpers import UnitFrom, are_columns_valid
from tests.conftest import mock_async_add_executor_job


class TestStandardImportIntegration:
    """Integration tests for standard (non-delta) column import functionality."""

    @pytest.mark.asyncio
    async def test_import_sum_single_statistic(self) -> None:
        """Test importing sum data for a single statistic (counter)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())  # Entity exists

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test sum CSV file
            test_file = Path(tmpdir) / "sum_test.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\n"
                "counter.energy\t01.01.2022 00:00\tkWh\t100.5\t100.5\n"
                "counter.energy\t01.01.2022 01:00\tkWh\t105.7\t105.7\n"
                "counter.energy\t01.01.2022 02:00\tkWh\t108.8\t108.8\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "sum_test.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                },
            )

            with patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import:
                await import_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                assert call_args is not None

                # Verify the metadata passed to import
                metadata = call_args[0][1]  # Second argument is metadata
                assert metadata["statistic_id"] == "counter.energy"
                assert metadata["source"] == "recorder"
                assert metadata["unit_of_measurement"] == "kWh"
                assert metadata["has_sum"] is True

                assert metadata["mean_type"] == StatisticMeanType.NONE

                # Verify the statistics list passed to import
                statistics = call_args[0][2]  # Third argument is statistics list
                assert len(statistics) == 3

                # Verify absolute values (no accumulation)
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(100.5)
                assert pytest.approx(statistics[0]["state"]) == pytest.approx(100.5)
                assert pytest.approx(statistics[1]["sum"]) == pytest.approx(105.7)
                assert pytest.approx(statistics[1]["state"]) == pytest.approx(105.7)
                assert pytest.approx(statistics[2]["sum"]) == pytest.approx(108.8)
                assert pytest.approx(statistics[2]["state"]) == pytest.approx(108.8)
                # Verify timestamps are datetime objects with UTC timezone
                assert isinstance(statistics[0]["start"], dt.datetime)
                assert statistics[0]["start"].tzinfo is not None

    @pytest.mark.asyncio
    async def test_import_mean_single_statistic(self) -> None:
        """Test importing mean/min/max data for a single statistic (sensor)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())  # Entity exists

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test mean CSV file
            test_file = Path(tmpdir) / "mean_test.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tmean\tmin\tmax\n"
                "sensor.temperature\t01.01.2022 00:00\t°C\t20.5\t18.2\t22.8\n"
                "sensor.temperature\t01.01.2022 01:00\t°C\t21.3\t19.1\t23.5\n"
                "sensor.temperature\t01.01.2022 02:00\t°C\t20.8\t18.5\t23.2\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "mean_test.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                },
            )

            with patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import:
                await import_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                assert call_args is not None

                # Verify the metadata passed to import
                metadata = call_args[0][1]  # Second argument is metadata
                assert metadata["statistic_id"] == "sensor.temperature"
                assert metadata["source"] == "recorder"
                assert metadata["unit_of_measurement"] == "°C"
                assert metadata["has_sum"] is False

                # Verify the statistics list passed to import
                statistics = call_args[0][2]  # Third argument is statistics list
                assert len(statistics) == 3

                # Verify values
                assert pytest.approx(statistics[0]["mean"]) == pytest.approx(20.5)
                assert pytest.approx(statistics[0]["min"]) == pytest.approx(18.2)
                assert pytest.approx(statistics[0]["max"]) == pytest.approx(22.8)
                assert pytest.approx(statistics[1]["mean"]) == pytest.approx(21.3)
                assert pytest.approx(statistics[1]["min"]) == pytest.approx(19.1)
                assert pytest.approx(statistics[1]["max"]) == pytest.approx(23.5)

    @pytest.mark.asyncio
    async def test_import_multiple_statistics(self) -> None:
        """Test importing data for multiple statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())  # Entities exist

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test CSV file with multiple statistics
            test_file = Path(tmpdir) / "multiple.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\n"
                "counter.energy\t01.01.2022 00:00\tkWh\t100.0\t100.0\n"
                "counter.energy\t01.01.2022 01:00\tkWh\t105.2\t105.2\n"
                "counter.gas\t01.01.2022 00:00\tm³\t50.0\t50.0\n"
                "counter.gas\t01.01.2022 01:00\tm³\t52.1\t52.1\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "multiple.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                },
            )

            with patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import:
                await import_handler(call)

                # Verify async_import_statistics was called for both statistics
                assert mock_import.call_count == 2

                # Collect calls by statistic_id
                calls_by_id = {}
                for call_obj in mock_import.call_args_list:
                    metadata = call_obj[0][1]
                    statistics = call_obj[0][2]
                    calls_by_id[metadata["statistic_id"]] = (metadata, statistics)

                # Verify counter.energy
                assert "counter.energy" in calls_by_id
                metadata_energy, stats_energy = calls_by_id["counter.energy"]
                assert metadata_energy["unit_of_measurement"] == "kWh"
                assert len(stats_energy) == 2
                assert pytest.approx(stats_energy[0]["sum"]) == pytest.approx(100.0)
                assert pytest.approx(stats_energy[1]["sum"]) == pytest.approx(105.2)

                # Verify counter.gas
                assert "counter.gas" in calls_by_id
                metadata_gas, stats_gas = calls_by_id["counter.gas"]
                assert metadata_gas["unit_of_measurement"] == "m³"
                assert len(stats_gas) == 2
                assert pytest.approx(stats_gas[0]["sum"]) == pytest.approx(50.0)
                assert pytest.approx(stats_gas[1]["sum"]) == pytest.approx(52.1)

    @pytest.mark.asyncio
    async def test_import_external_statistic(self) -> None:
        """Test importing data for external statistics (custom domain)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=None)  # No entity needed for external

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test CSV file with external statistic
            test_file = Path(tmpdir) / "external.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\n"
                "custom:external_counter\t01.01.2022 00:00\tkWh\t200.0\t200.0\n"
                "custom:external_counter\t01.01.2022 01:00\tkWh\t205.2\t205.2\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "external.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                },
            )

            with patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_import:
                await import_handler(call)

                # Verify async_add_external_statistics was called
                assert mock_import.called, "async_add_external_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                metadata = call_args[0][1]
                statistics = call_args[0][2]

                # Verify metadata for external statistic
                assert metadata["statistic_id"] == "custom:external_counter"
                assert metadata["source"] == "custom"
                assert metadata["unit_of_measurement"] == "kWh"
                assert metadata["has_sum"] is True

                # Verify values
                assert len(statistics) == 2
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(200.0)
                assert pytest.approx(statistics[0]["state"]) == pytest.approx(200.0)
                assert pytest.approx(statistics[1]["sum"]) == pytest.approx(205.2)
                assert pytest.approx(statistics[1]["state"]) == pytest.approx(205.2)

    @pytest.mark.asyncio
    async def test_import_without_unit_column(self) -> None:
        """Test importing data without unit column when unit_from_entity is True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()

            # Mock entity with unit_of_measurement attribute
            mock_entity = MagicMock()
            mock_entity.attributes = {"unit_of_measurement": "°C"}
            hass.states.get = MagicMock(return_value=mock_entity)
            hass.states.set = MagicMock()

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test CSV file without unit column
            test_file = Path(tmpdir) / "no_unit.csv"
            test_file.write_text(
                "statistic_id\tstart\tmean\tmin\tmax\n"
                "sensor.temperature\t01.01.2022 00:00\t20.5\t18.2\t22.8\n"
                "sensor.temperature\t01.01.2022 01:00\t21.3\t19.1\t23.5\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "no_unit.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                    ATTR_UNIT_FROM_ENTITY: True,
                },
            )

            with patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import:
                await import_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                metadata = call_args[0][1]

                # Verify unit was extracted from entity
                assert metadata["unit_of_measurement"] == "°C"

    @pytest.mark.asyncio
    async def test_import_json_format_sum(self) -> None:
        """Test importing sum data from JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            json_handler = hass.services.register.call_args_list[1][0][2]

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_json",
                {
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DECIMAL: False,
                    "entities": [
                        {
                            "id": "counter.energy",
                            "unit": "kWh",
                            "values": [
                                {"datetime": "01.01.2022 00:00", "sum": 100.0, "state": 100.0},
                                {"datetime": "01.01.2022 01:00", "sum": 105.2, "state": 105.2},
                            ],
                        }
                    ],
                },
            )

            with patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import:
                await json_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                metadata = call_args[0][1]
                statistics = call_args[0][2]

                # Verify metadata
                assert metadata["statistic_id"] == "counter.energy"
                assert metadata["source"] == "recorder"
                assert metadata["unit_of_measurement"] == "kWh"
                assert metadata["has_sum"] is True

                # Verify values from JSON
                assert len(statistics) == 2
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(100.0)
                assert pytest.approx(statistics[0]["state"]) == pytest.approx(100.0)
                assert pytest.approx(statistics[1]["sum"]) == pytest.approx(105.2)
                assert pytest.approx(statistics[1]["state"]) == pytest.approx(105.2)

    @pytest.mark.asyncio
    async def test_import_json_format_mean(self) -> None:
        """Test importing mean/min/max data from JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            json_handler = hass.services.register.call_args_list[1][0][2]

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_json",
                {
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DECIMAL: False,
                    "entities": [
                        {
                            "id": "sensor.temperature",
                            "unit": "°C",
                            "values": [
                                {
                                    "datetime": "01.01.2022 00:00",
                                    "mean": 20.5,
                                    "min": 18.2,
                                    "max": 22.8,
                                },
                                {
                                    "datetime": "01.01.2022 01:00",
                                    "mean": 21.3,
                                    "min": 19.1,
                                    "max": 23.5,
                                },
                            ],
                        }
                    ],
                },
            )

            with patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import:
                await json_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                metadata = call_args[0][1]
                statistics = call_args[0][2]

                # Verify metadata
                assert metadata["statistic_id"] == "sensor.temperature"
                assert metadata["unit_of_measurement"] == "°C"
                assert metadata["has_sum"] is False

                # Verify values from JSON
                assert len(statistics) == 2
                assert pytest.approx(statistics[0]["mean"]) == pytest.approx(20.5)
                assert pytest.approx(statistics[0]["min"]) == pytest.approx(18.2)
                assert pytest.approx(statistics[0]["max"]) == pytest.approx(22.8)

    @pytest.mark.asyncio
    async def test_import_decimal_comma(self) -> None:
        """Test importing data with decimal comma instead of decimal point."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test CSV file with comma as decimal separator
            test_file = Path(tmpdir) / "comma.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\n"
                "counter.energy\t01.01.2022 00:00\tkWh\t100,5\t100,5\n"
                "counter.energy\t01.01.2022 01:00\tkWh\t105,7\t105,7\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "comma.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: True,
                },
            )

            with patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import:
                await import_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                statistics = call_args[0][2]

                # Verify decimal comma was converted correctly
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(100.5)
                assert pytest.approx(statistics[1]["sum"]) == pytest.approx(105.7)

    @pytest.mark.asyncio
    async def test_import_with_different_timezone(self) -> None:
        """Test importing data with different timezone conversion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test CSV file
            test_file = Path(tmpdir) / "tz_test.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\n"
                "counter.energy\t01.01.2022 01:00\tkWh\t100.0\t100.0\n"
                "counter.energy\t01.01.2022 02:00\tkWh\t105.2\t105.2\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "tz_test.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "Europe/Vienna",  # UTC+1 in January
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                },
            )

            with patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import:
                await import_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                statistics = call_args[0][2]

                # Verify timestamps were parsed with timezone info
                assert isinstance(statistics[0]["start"], dt.datetime)
                assert statistics[0]["start"].tzinfo is not None
                # Timestamps should be in Europe/Vienna timezone
                assert len(statistics) == 2
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(100.0)
                assert pytest.approx(statistics[1]["sum"]) == pytest.approx(105.2)

    @pytest.mark.asyncio
    async def test_import_mixed_sum_and_mean_fails(self) -> None:
        """Test that mixing sum and mean columns fails validation."""
        # Create a dataframe with both sum and mean
        df = pd.DataFrame(
            {
                "statistic_id": ["counter.energy"],
                "start": ["01.01.2022 00:00"],
                "unit": ["kWh"],
                "sum": [100.0],
                "mean": [50.0],
            }
        )

        # Should raise error when both sum and mean are present
        with pytest.raises(HomeAssistantError):
            are_columns_valid(df, UnitFrom.TABLE)

    @pytest.mark.asyncio
    async def test_import_missing_required_columns(self) -> None:
        """Test that missing required columns raises error."""
        # Create a dataframe missing start column
        df = pd.DataFrame(
            {
                "statistic_id": ["counter.energy"],
                "unit": ["kWh"],
                "sum": [100.0],
            }
        )

        # Should raise error when required columns are missing
        with pytest.raises(HomeAssistantError):
            are_columns_valid(df, UnitFrom.TABLE)

    @pytest.mark.asyncio
    async def test_import_entity_not_exists(self) -> None:
        """Test that importing for non-existent entity raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=None)  # Entity does not exist

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test CSV file
            test_file = Path(tmpdir) / "nonexistent.csv"
            test_file.write_text("statistic_id\tstart\tunit\tsum\tstate\nsensor.nonexistent\t01.01.2022 00:00\t°C\t20.5\t20.5\n")

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "nonexistent.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                },
            )

            # Should raise error when entity does not exist
            with pytest.raises(HomeAssistantError):
                await import_handler(call)

    @pytest.mark.asyncio
    async def test_import_with_custom_datetime_format(self) -> None:
        """Test importing data with custom datetime format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test CSV file with ISO format
            test_file = Path(tmpdir) / "iso_format.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\n"
                "counter.energy\t2022-01-01 00:00\tkWh\t100.0\t100.0\n"
                "counter.energy\t2022-01-01 01:00\tkWh\t105.2\t105.2\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "iso_format.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                    ATTR_DATETIME_FORMAT: "%Y-%m-%d %H:%M",
                },
            )

            with patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import:
                await import_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                statistics = call_args[0][2]

                # Verify data was parsed correctly
                assert len(statistics) == 2
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_import_multiple_external_statistics(self) -> None:
        """Test importing multiple external statistics in one file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=None)

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test CSV file with multiple external statistics
            test_file = Path(tmpdir) / "multi_external.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tsum\tstate\n"
                "custom:external1\t01.01.2022 00:00\tkWh\t100.0\t100.0\n"
                "custom:external1\t01.01.2022 01:00\tkWh\t105.2\t105.2\n"
                "integration:external2\t01.01.2022 00:00\tm³\t50.0\t50.0\n"
                "integration:external2\t01.01.2022 01:00\tm³\t52.1\t52.1\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "multi_external.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                },
            )

            with patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_external:
                await import_handler(call)

                # Verify async_add_external_statistics was called for both external statistics
                assert mock_external.call_count == 2

                # Collect calls by statistic_id
                calls_by_id = {}
                for call_obj in mock_external.call_args_list:
                    metadata = call_obj[0][1]
                    statistics = call_obj[0][2]
                    calls_by_id[metadata["statistic_id"]] = (metadata, statistics)

                # Verify custom:external1
                assert "custom:external1" in calls_by_id
                metadata_ext1, stats_ext1 = calls_by_id["custom:external1"]
                assert metadata_ext1["source"] == "custom"
                assert metadata_ext1["unit_of_measurement"] == "kWh"
                assert len(stats_ext1) == 2
                assert pytest.approx(stats_ext1[0]["sum"]) == pytest.approx(100.0)
                assert pytest.approx(stats_ext1[1]["sum"]) == pytest.approx(105.2)

                # Verify integration:external2
                assert "integration:external2" in calls_by_id
                metadata_ext2, stats_ext2 = calls_by_id["integration:external2"]
                assert metadata_ext2["source"] == "integration"
                assert metadata_ext2["unit_of_measurement"] == "m³"
                assert len(stats_ext2) == 2
                assert pytest.approx(stats_ext2[0]["sum"]) == pytest.approx(50.0)
                assert pytest.approx(stats_ext2[1]["sum"]) == pytest.approx(52.1)
