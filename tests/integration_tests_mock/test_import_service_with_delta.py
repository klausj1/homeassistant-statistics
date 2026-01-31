"""Integration tests for delta column import feature."""

import datetime as dt
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import async_setup
from custom_components.import_statistics.const import (
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_FILENAME,
    ATTR_TIMEZONE_IDENTIFIER,
)
from custom_components.import_statistics.helpers import DeltaReferenceType, UnitFrom, are_columns_valid
from custom_components.import_statistics.import_service_delta_helper import convert_deltas_with_older_reference, handle_dataframe_delta
from tests.conftest import create_mock_recorder_instance, mock_async_add_executor_job


class TestDeltaImportIntegration:
    """Integration tests for delta column import functionality."""

    @pytest.mark.asyncio
    async def test_import_delta_single_statistic(self) -> None:
        """Test importing delta data for a single statistic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())  # Entity exists

            await async_setup(hass, {})
            import_handler = hass.services.async_register.call_args_list[0][0][2]

            # Create test delta CSV file
            test_file = Path(tmpdir) / "delta_test.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tdelta\n"
                "counter.energy\t01.01.2022 00:00\tkWh\t10.5\n"
                "counter.energy\t01.01.2022 01:00\tkWh\t5.2\n"
                "counter.energy\t01.01.2022 02:00\tkWh\t3.1\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "delta_test.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            # Mock the database query for oldest statistics
            mock_reference = {
                "counter.energy": {
                    "reference": {
                        "start": None,  # Not used in this test
                        "sum": 100.0,  # Reference sum value
                        "state": 200.0,  # Reference state value
                    },
                    "ref_type": DeltaReferenceType.OLDER_REFERENCE,
                }
            }

            with (
                patch("custom_components.import_statistics.import_service.prepare_delta_handling", new_callable=AsyncMock) as mock_prepare_delta,
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            ):
                mock_prepare_delta.return_value = mock_reference
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

                # Verify accumulated values (using approximate equality for floating point)
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(110.5)
                assert pytest.approx(statistics[0]["state"]) == pytest.approx(210.5)
                assert pytest.approx(statistics[1]["sum"]) == pytest.approx(115.7)
                assert pytest.approx(statistics[1]["state"]) == pytest.approx(215.7)
                assert pytest.approx(statistics[2]["sum"]) == pytest.approx(118.8)
                assert pytest.approx(statistics[2]["state"]) == pytest.approx(218.8)
                # Verify timestamps are datetime objects with UTC timezone
                assert isinstance(statistics[0]["start"], dt.datetime)
                assert statistics[0]["start"].tzinfo is not None

    @pytest.mark.asyncio
    async def test_import_delta_multiple_statistics(self) -> None:
        """Test importing delta data for multiple statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())  # Entities exist

            await async_setup(hass, {})
            import_handler = hass.services.async_register.call_args_list[0][0][2]

            # Create test delta CSV file with multiple statistics
            test_file = Path(tmpdir) / "delta_multiple.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tdelta\n"
                "counter.energy\t01.01.2022 00:00\tkWh\t10.5\n"
                "counter.energy\t01.01.2022 01:00\tkWh\t5.2\n"
                "counter.gas\t01.01.2022 00:00\tm³\t1.5\n"
                "counter.gas\t01.01.2022 01:00\tm³\t2.1\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "delta_multiple.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            # Mock the database query for oldest statistics
            mock_reference = {
                "counter.energy": {"reference": {"start": None, "sum": 100.0, "state": 100.0}, "ref_type": DeltaReferenceType.OLDER_REFERENCE},
                "counter.gas": {"reference": {"start": None, "sum": 50.0, "state": 50.0}, "ref_type": DeltaReferenceType.OLDER_REFERENCE},
            }

            with (
                patch("custom_components.import_statistics.import_service.prepare_delta_handling", new_callable=AsyncMock) as mock_prepare_delta,
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            ):
                mock_prepare_delta.return_value = mock_reference
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
                # Verify accumulated delta values: 100.0 + 10.5 = 110.5, then 110.5 + 5.2 = 115.7
                assert pytest.approx(stats_energy[0]["sum"]) == pytest.approx(110.5)
                assert pytest.approx(stats_energy[1]["sum"]) == pytest.approx(115.7)

                # Verify counter.gas
                assert "counter.gas" in calls_by_id
                metadata_gas, stats_gas = calls_by_id["counter.gas"]
                assert metadata_gas["unit_of_measurement"] == "m³"
                assert len(stats_gas) == 2
                # Verify accumulated delta values: 50.0 + 1.5 = 51.5, then 51.5 + 2.1 = 53.6
                assert pytest.approx(stats_gas[0]["sum"]) == pytest.approx(51.5)
                assert pytest.approx(stats_gas[1]["sum"]) == pytest.approx(53.6)

    @pytest.mark.asyncio
    async def test_import_delta_with_negative_values(self) -> None:
        """Test importing delta data with negative delta values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())  # Entity exists

            await async_setup(hass, {})
            import_handler = hass.services.async_register.call_args_list[0][0][2]

            # Create test delta CSV file with negative values
            test_file = Path(tmpdir) / "delta_negative.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tdelta\n"
                "counter.energy\t01.01.2022 00:00\tkWh\t-10.5\n"
                "counter.energy\t01.01.2022 01:00\tkWh\t-5.2\n"
                "counter.energy\t01.01.2022 02:00\tkWh\t3.1\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "delta_negative.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            # Mock the database query for oldest statistics
            mock_reference = {"counter.energy": {"reference": {"start": None, "sum": 100.0, "state": 100.0}, "ref_type": DeltaReferenceType.OLDER_REFERENCE}}

            with (
                patch("custom_components.import_statistics.import_service.prepare_delta_handling", new_callable=AsyncMock) as mock_prepare_delta,
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            ):
                mock_prepare_delta.return_value = mock_reference
                await import_handler(call)

                # Verify async_import_statistics was called
                assert mock_import.called, "async_import_statistics should have been called"

                # Extract the call arguments
                call_args = mock_import.call_args
                statistics = call_args[0][2]
                assert len(statistics) == 3

                # Verify accumulated values with negative deltas
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(89.5)
                assert pytest.approx(statistics[0]["state"]) == pytest.approx(89.5)
                assert pytest.approx(statistics[1]["sum"]) == pytest.approx(84.3)
                assert pytest.approx(statistics[1]["state"]) == pytest.approx(84.3)
                assert pytest.approx(statistics[2]["sum"]) == pytest.approx(87.4)
                assert pytest.approx(statistics[2]["state"]) == pytest.approx(87.4)

    @pytest.mark.asyncio
    async def test_import_delta_external_statistic(self) -> None:
        """Test importing delta data for external statistics (custom domain)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=None)  # No entity needed for external

            await async_setup(hass, {})
            import_handler = hass.services.async_register.call_args_list[0][0][2]

            # Create test delta CSV file with external statistic
            test_file = Path(tmpdir) / "delta_external.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tdelta\ncustom:external_counter\t01.01.2022 00:00\tkWh\t10.5\ncustom:external_counter\t01.01.2022 01:00\tkWh\t5.2\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "delta_external.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            # Mock the database query for oldest statistics
            mock_reference = {
                "custom:external_counter": {"reference": {"start": None, "sum": 200.0, "state": 200.0}, "ref_type": DeltaReferenceType.OLDER_REFERENCE}
            }

            with (
                patch("custom_components.import_statistics.import_service.prepare_delta_handling", new_callable=AsyncMock) as mock_prepare_delta,
                patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            ):
                mock_prepare_delta.return_value = mock_reference
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

                # Verify accumulated values match the external counter ID
                assert len(statistics) == 2
                # 200.0 + 10.5 = 210.5, then 210.5 + 5.2 = 215.7
                assert pytest.approx(statistics[0]["sum"]) == pytest.approx(210.5)
                assert pytest.approx(statistics[0]["state"]) == pytest.approx(210.5)
                assert pytest.approx(statistics[1]["sum"]) == pytest.approx(215.7)
                assert pytest.approx(statistics[1]["state"]) == pytest.approx(215.7)

    @pytest.mark.asyncio
    async def test_import_delta_without_hass_fails(self) -> None:
        """Test that delta import with missing references raises error."""
        # Create a delta dataframe
        df = pd.DataFrame(
            {
                "statistic_id": ["counter.energy"],
                "start": ["01.01.2022 00:00"],
                "unit": ["kWh"],
                "delta": [10.5],
            }
        )

        # References with None for the statistic (no reference found)
        references = {"counter.energy": None}

        # Should raise error when reference is None for delta data
        with pytest.raises(HomeAssistantError):
            handle_dataframe_delta(
                df,
                "UTC",
                "%d.%m.%Y %H:%M",
                UnitFrom.TABLE,
                references,
            )

    @pytest.mark.asyncio
    async def test_import_delta_data_accumulation(self) -> None:
        """Test that delta values are correctly accumulated to absolute sum/state values."""
        # Create delta rows
        delta_rows = [
            {"start": dt.datetime(2022, 1, 1, 0, 0, tzinfo=dt.UTC), "delta": 10.5},
            {"start": dt.datetime(2022, 1, 1, 1, 0, tzinfo=dt.UTC), "delta": 5.2},
            {"start": dt.datetime(2022, 1, 1, 2, 0, tzinfo=dt.UTC), "delta": 3.1},
        ]

        # Reference values
        sum_oldest = 100.0
        state_oldest = 100.0

        # Convert
        result = convert_deltas_with_older_reference(delta_rows, sum_oldest, state_oldest)

        # Verify accumulation
        assert len(result) == 3
        assert result[0]["sum"] == 110.5  # 100.0 + 10.5
        assert result[0]["state"] == 110.5
        assert result[1]["sum"] == 115.7  # 110.5 + 5.2
        assert result[1]["state"] == 115.7
        assert result[2]["sum"] == 118.8  # 115.7 + 3.1
        assert result[2]["state"] == 118.8

    @pytest.mark.asyncio
    async def test_import_delta_json_format(self) -> None:
        """Test importing delta data from JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = mock_async_add_executor_job
            hass.states = MagicMock()
            hass.states.set = MagicMock()
            hass.states.get = MagicMock(return_value=MagicMock())

            await async_setup(hass, {})
            json_handler = hass.services.async_register.call_args_list[1][0][2]

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
                                {"datetime": "01.01.2022 00:00", "sum": 110.5, "state": 110.5},
                                {"datetime": "01.01.2022 01:00", "sum": 115.7, "state": 115.7},
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

                # Verify accumulated values from JSON
                assert len(statistics) == 2, "Should have 2 statistics rows"
                assert pytest.approx(statistics[0]["sum"]) == 110.5
                assert pytest.approx(statistics[0]["state"]) == 110.5
                assert pytest.approx(statistics[1]["sum"]) == 115.7
                assert pytest.approx(statistics[1]["state"]) == 115.7

    @pytest.mark.asyncio
    async def test_delta_reference_validation_failure(self) -> None:
        """Test that missing database reference is properly handled."""
        # Create a delta dataframe
        df = pd.DataFrame(
            {
                "statistic_id": ["counter.energy"],
                "start": ["01.01.2022 00:00"],
                "unit": ["kWh"],
                "delta": [10.5],
            }
        )

        # References with None for the statistic (no reference found)
        references = {"counter.energy": None}

        # Should raise error when reference is None
        with pytest.raises(HomeAssistantError):
            handle_dataframe_delta(
                df,
                "UTC",
                "%d.%m.%Y %H:%M",
                UnitFrom.TABLE,
                references,
            )

    @pytest.mark.asyncio
    async def test_delta_column_with_incompatible_columns(self) -> None:
        """Test that delta column cannot coexist with sum/state/mean columns."""
        # Test delta + sum
        df_with_sum = pd.DataFrame(
            {
                "statistic_id": ["counter.energy"],
                "start": ["01.01.2022 00:00"],
                "unit": ["kWh"],
                "delta": [10.5],
                "sum": [100.0],
            }
        )

        with pytest.raises(HomeAssistantError):
            are_columns_valid(df_with_sum, UnitFrom.TABLE)

        # Test delta + mean
        df_with_mean = pd.DataFrame(
            {
                "statistic_id": ["sensor.temp"],
                "start": ["01.01.2022 00:00"],
                "unit": ["°C"],
                "delta": [1.5],
                "mean": [20.5],
            }
        )

        with pytest.raises(HomeAssistantError):
            are_columns_valid(df_with_mean, UnitFrom.TABLE)
