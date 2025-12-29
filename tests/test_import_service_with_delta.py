"""Integration tests for delta column import feature."""

import datetime as dt
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import prepare_data, setup
from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_FILENAME,
    ATTR_TIMEZONE_IDENTIFIER,
    ATTR_UNIT_FROM_ENTITY,
)
from custom_components.import_statistics.helpers import UnitFrom
from tests.conftest import mock_async_add_executor_job


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

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

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
                    ATTR_DECIMAL: False,
                },
            )

            # Mock the database query for oldest statistics
            mock_reference = {
                "counter.energy": {
                    "start": None,  # Not used in this test
                    "sum": 100.0,   # Reference sum value
                    "state": 200.0, # Reference state value
                }
            }

            with patch("custom_components.import_statistics.get_oldest_statistics_before") as mock_get_oldest:
                with patch("custom_components.import_statistics.async_import_statistics") as mock_import:
                    mock_get_oldest.return_value = mock_reference
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
                    from homeassistant.components.recorder.models import StatisticMeanType
                    assert metadata["mean_type"] == StatisticMeanType.NONE

                    # Verify the statistics list passed to import
                    statistics = call_args[0][2]  # Third argument is statistics list
                    assert len(statistics) == 3, "Should have 3 statistics rows"

                    # Verify accumulated values (using approximate equality for floating point)
                    assert pytest.approx(statistics[0]["sum"]) == 110.5  # 100.0 + 10.5
                    assert pytest.approx(statistics[0]["state"]) == 210.5
                    assert pytest.approx(statistics[1]["sum"]) == 115.7  # 110.5 + 5.2
                    assert pytest.approx(statistics[1]["state"]) == 215.7
                    assert pytest.approx(statistics[2]["sum"]) == 118.8  # 115.7 + 3.1
                    assert pytest.approx(statistics[2]["state"]) == 218.8
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

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

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
                    ATTR_DECIMAL: False,
                },
            )

            # Mock the database query for oldest statistics
            mock_reference = {
                "counter.energy": {"start": None, "sum": 100.0, "state": 100.0},
                "counter.gas": {"start": None, "sum": 50.0, "state": 50.0},
            }

            with patch("custom_components.import_statistics.get_oldest_statistics_before") as mock_get_oldest:
                with patch("custom_components.import_statistics.async_import_statistics") as mock_import:
                    mock_get_oldest.return_value = mock_reference
                    await import_handler(call)

                    # Verify async_import_statistics was called for both statistics
                    assert mock_import.call_count == 2, "async_import_statistics should be called twice"

                    # Verify first statistic (counter.energy)
                    first_call = mock_import.call_args_list[0]
                    metadata_1 = first_call[0][1]
                    statistics_1 = first_call[0][2]
                    assert metadata_1["statistic_id"] in ["counter.energy", "counter.gas"]
                    assert len(statistics_1) == 2, "counter.energy should have 2 statistics rows"

                    # Verify second statistic (counter.gas)
                    second_call = mock_import.call_args_list[1]
                    metadata_2 = second_call[0][1]
                    statistics_2 = second_call[0][2]
                    assert metadata_2["statistic_id"] in ["counter.energy", "counter.gas"]
                    assert len(statistics_2) == 2, "counter.gas should have 2 statistics rows"

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

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

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
                    ATTR_DECIMAL: False,
                },
            )

            # Mock the database query for oldest statistics
            mock_reference = {
                "counter.energy": {"start": None, "sum": 100.0, "state": 100.0}
            }

            with patch("custom_components.import_statistics.get_oldest_statistics_before") as mock_get_oldest:
                with patch("custom_components.import_statistics.async_import_statistics") as mock_import:
                    mock_get_oldest.return_value = mock_reference
                    await import_handler(call)

                    # Verify async_import_statistics was called
                    assert mock_import.called, "async_import_statistics should have been called"

                    # Extract the call arguments
                    call_args = mock_import.call_args
                    statistics = call_args[0][2]
                    assert len(statistics) == 3, "Should have 3 statistics rows"

                    # Verify accumulated values with negative deltas
                    assert pytest.approx(statistics[0]["sum"]) == 89.5  # 100.0 + (-10.5)
                    assert pytest.approx(statistics[0]["state"]) == 89.5
                    assert pytest.approx(statistics[1]["sum"]) == 84.3  # 89.5 + (-5.2)
                    assert pytest.approx(statistics[1]["state"]) == 84.3
                    assert pytest.approx(statistics[2]["sum"]) == 87.4  # 84.3 + 3.1
                    assert pytest.approx(statistics[2]["state"]) == 87.4

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

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

            # Create test delta CSV file with external statistic
            test_file = Path(tmpdir) / "delta_external.csv"
            test_file.write_text(
                "statistic_id\tstart\tunit\tdelta\n"
                "custom:external_counter\t01.01.2022 00:00\tkWh\t10.5\n"
                "custom:external_counter\t01.01.2022 01:00\tkWh\t5.2\n"
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "delta_external.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                },
            )

            # Mock the database query for oldest statistics
            mock_reference = {
                "custom:external_counter": {"start": None, "sum": 200.0, "state": 200.0}
            }

            with patch("custom_components.import_statistics.get_oldest_statistics_before") as mock_get_oldest:
                with patch("custom_components.import_statistics.async_add_external_statistics") as mock_import:
                    mock_get_oldest.return_value = mock_reference
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

                    # Verify accumulated values
                    assert len(statistics) == 2, "Should have 2 statistics rows"
                    assert pytest.approx(statistics[0]["sum"]) == 210.5  # 200.0 + 10.5
                    assert pytest.approx(statistics[0]["state"]) == 210.5
                    assert pytest.approx(statistics[1]["sum"]) == 215.7  # 210.5 + 5.2
                    assert pytest.approx(statistics[1]["state"]) == 215.7

    @pytest.mark.asyncio
    async def test_import_delta_without_hass_fails(self) -> None:
        """Test that delta import without hass parameter raises error."""
        from custom_components.import_statistics import prepare_data
        from homeassistant.exceptions import HomeAssistantError

        import pandas as pd

        # Create a delta dataframe
        df = pd.DataFrame({
            "statistic_id": ["counter.energy"],
            "start": ["01.01.2022 00:00"],
            "unit": ["kWh"],
            "delta": [10.5],
        })

        # Should raise error when hass is None and delta is detected
        with pytest.raises(HomeAssistantError):
            prepare_data.handle_dataframe(
                df,
                "UTC",
                "%d.%m.%Y %H:%M",
                prepare_data.UnitFrom.TABLE,
                hass=None,
            )

    @pytest.mark.asyncio
    async def test_import_delta_data_accumulation(self) -> None:
        """Test that delta values are correctly accumulated to absolute sum/state values."""
        from custom_components.import_statistics.prepare_data import convert_deltas_case_1
        import datetime as dt

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
        result = convert_deltas_case_1(delta_rows, sum_oldest, state_oldest)

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
                                {"datetime": "01.01.2022 00:00", "sum": 110.5, "state": 110.5},
                                {"datetime": "01.01.2022 01:00", "sum": 115.7, "state": 115.7},
                            ],
                        }
                    ],
                },
            )

            with patch("custom_components.import_statistics.async_import_statistics") as mock_import:
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
        df = pd.DataFrame({
            "statistic_id": ["counter.energy"],
            "start": ["01.01.2022 00:00"],
            "unit": ["kWh"],
            "delta": [10.5],
        })

        # References with None for the statistic (no reference found)
        references = {
            "counter.energy": None
        }

        # Should raise error when reference is None
        with pytest.raises(HomeAssistantError):
            prepare_data.convert_delta_dataframe_with_references(
                df,
                references,
                "UTC",
                "%d.%m.%Y %H:%M",
                UnitFrom.TABLE,
            )

    @pytest.mark.asyncio
    async def test_delta_column_with_incompatible_columns(self) -> None:
        """Test that delta column cannot coexist with sum/state/mean columns."""
        from homeassistant.exceptions import HomeAssistantError
        from custom_components.import_statistics.helpers import are_columns_valid, UnitFrom
        import pandas as pd

        # Test delta + sum
        df_with_sum = pd.DataFrame({
            "statistic_id": ["counter.energy"],
            "start": ["01.01.2022 00:00"],
            "unit": ["kWh"],
            "delta": [10.5],
            "sum": [100.0],
        })

        with pytest.raises(HomeAssistantError):
            are_columns_valid(df_with_sum, UnitFrom.TABLE)

        # Test delta + mean
        df_with_mean = pd.DataFrame({
            "statistic_id": ["sensor.temp"],
            "start": ["01.01.2022 00:00"],
            "unit": ["°C"],
            "delta": [1.5],
            "mean": [20.5],
        })

        with pytest.raises(HomeAssistantError):
            are_columns_valid(df_with_mean, UnitFrom.TABLE)
