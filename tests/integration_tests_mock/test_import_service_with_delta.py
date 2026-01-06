"""Integration tests for delta column import feature."""

import datetime as dt
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import setup
from custom_components.import_statistics.const import (
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_FILENAME,
    ATTR_TIMEZONE_IDENTIFIER,
)
from custom_components.import_statistics.helpers import DeltaReferenceType, UnitFrom, are_columns_valid
from custom_components.import_statistics.import_service_delta_helper import convert_deltas_with_older_reference, handle_dataframe_delta
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
                "counter.energy": {"reference": {"start": None, "sum": 100.0, "state": 100.0}, "ref_type": DeltaReferenceType.OLDER_REFERENCE},
                "counter.gas": {"reference": {"start": None, "sum": 50.0, "state": 50.0}, "ref_type": DeltaReferenceType.OLDER_REFERENCE},
            }

            with (
                patch("custom_components.import_statistics.import_service.prepare_delta_handling", new_callable=AsyncMock) as mock_prepare_delta,
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
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
            mock_reference = {"counter.energy": {"reference": {"start": None, "sum": 100.0, "state": 100.0}, "ref_type": DeltaReferenceType.OLDER_REFERENCE}}

            with (
                patch("custom_components.import_statistics.import_service.prepare_delta_handling", new_callable=AsyncMock) as mock_prepare_delta,
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
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

            setup(hass, {})
            import_handler = hass.services.register.call_args_list[0][0][2]

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
                    ATTR_DECIMAL: False,
                },
            )

            # Mock the database query for oldest statistics
            mock_reference = {
                "custom:external_counter": {"reference": {"start": None, "sum": 200.0, "state": 200.0}, "ref_type": DeltaReferenceType.OLDER_REFERENCE}
            }

            with (
                patch("custom_components.import_statistics.import_service.prepare_delta_handling", new_callable=AsyncMock) as mock_prepare_delta,
                patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_import,
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

    @pytest.mark.asyncio
    async def test_import_delta_with_configurable_mock_data(self) -> None:
        """Test importing delta data using configurable mock data from files."""
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

            # Load test data from files
            import_file_path = Path(__file__).parent.parent.parent / "config" / "test_delta" / "test_case_1_sum_delta_changed.txt"
            db_file_path = Path(__file__).parent.parent.parent / "config" / "test_delta" / "test_case_1_sum_state.txt"
            expected_file_path = Path(__file__).parent.parent.parent / "config" / "test_delta" / "expected_after_step3_delta_changed.tsv"

            expected_df = pd.read_csv(expected_file_path, sep="\t")
            db_df = pd.read_csv(db_file_path, sep="\t")
            import_df = pd.read_csv(import_file_path, sep="\t")

            # Create test delta file with all data
            test_file = Path(tmpdir) / "delta_test_all.csv"
            import_df.to_csv(test_file, sep="\t", index=False)

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "delta_test_all.csv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                },
            )

            # Create mock functions for delta import helper functions
            with (
                patch("custom_components.import_statistics.import_service._get_newest_db_statistic", new_callable=AsyncMock) as mock_newest,
                patch("custom_components.import_statistics.import_service._get_reference_before_timestamp", new_callable=AsyncMock) as mock_before,
                patch("custom_components.import_statistics.import_service._get_reference_at_or_after_timestamp", new_callable=AsyncMock) as mock_after,
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_import_ext,
            ):
                # Configure mock behaviors based on test data
                self._configure_delta_mocks(mock_newest, mock_before, mock_after, import_df, db_df)

                await import_handler(call)

                assert mock_import.called or mock_import_ext.called, "Import methods should have been called"

                calls_by_id = self._collect_import_calls(mock_import, mock_import_ext)

                self._verify_all_statistics(calls_by_id, expected_df)

    @staticmethod
    def _build_mock_reference(import_test_case_1: pd.DataFrame, db_test_case_1: pd.DataFrame) -> dict:
        """Build mock reference data from database entries."""
        mock_reference = {}

        for entity_id in import_test_case_1["statistic_id"].unique():
            import_entity = import_test_case_1[import_test_case_1["statistic_id"] == entity_id]
            db_entity = db_test_case_1[db_test_case_1["statistic_id"] == entity_id]

            if len(import_entity) > 0 and len(db_entity) > 0:
                oldest_import_start = import_entity["start"].iloc[0]
                import_time = pd.to_datetime(oldest_import_start, format="%d.%m.%Y %H:%M")
                db_entity_with_time = db_entity.copy()
                db_entity_with_time["datetime"] = pd.to_datetime(db_entity["start"], format="%d.%m.%Y %H:%M")

                older_records = db_entity_with_time[db_entity_with_time["datetime"] < import_time]

                if len(older_records) > 0:
                    reference_record = older_records.iloc[-1]
                    mock_reference[entity_id] = {
                        "reference": {
                            "start": None,
                            "sum": float(reference_record["sum"]),
                            "state": float(reference_record["state"]),
                        },
                        "ref_type": DeltaReferenceType.OLDER_REFERENCE,
                    }

        return mock_reference

    def _configure_delta_mocks(self, mock_newest: AsyncMock, mock_before: AsyncMock, mock_after: AsyncMock, import_test_case_1: pd.DataFrame, db_test_case_1: pd.DataFrame) -> None:
        """Configure mocks for delta import helper functions based on test data."""
        # Parse datetime from both dataframes
        import_test_case_1_copy = import_test_case_1.copy()
        import_test_case_1_copy["datetime"] = pd.to_datetime(import_test_case_1_copy["start"], format="%d.%m.%Y %H:%M")
        db_test_case_1_copy = db_test_case_1.copy()
        db_test_case_1_copy["datetime"] = pd.to_datetime(db_test_case_1_copy["start"], format="%d.%m.%Y %H:%M")

        # Store entity metadata for mock functions
        entity_metadata: dict[str, Any] = {}

        for entity_id in import_test_case_1["statistic_id"].unique():
            import_entity = import_test_case_1_copy[import_test_case_1_copy["statistic_id"] == entity_id]
            db_entity = db_test_case_1_copy[db_test_case_1_copy["statistic_id"] == entity_id]

            if len(import_entity) == 0 or len(db_entity) == 0:
                continue

            # Get oldest and newest import times
            t_oldest_import = import_entity["datetime"].min()
            t_newest_import = import_entity["datetime"].max()

            # Get oldest and newest DB times
            t_oldest_db = db_entity["datetime"].min()
            t_newest_db = db_entity["datetime"].max()

            # Convert to UTC (add timezone info)
            t_oldest_import_utc = t_oldest_import.replace(tzinfo=dt.UTC)
            t_newest_import_utc = t_newest_import.replace(tzinfo=dt.UTC)
            t_oldest_db_utc = t_oldest_db.replace(tzinfo=dt.UTC)
            t_newest_db_utc = t_newest_db.replace(tzinfo=dt.UTC)

            # Store metadata for this entity
            entity_metadata[entity_id] = {
                "t_oldest_import": t_oldest_import_utc,
                "t_newest_import": t_newest_import_utc,
                "t_oldest_db": t_oldest_db_utc,
                "t_newest_db": t_newest_db_utc,
                "db_entity": db_entity,
                "newest_db_record": db_entity.iloc[-1],
            }

        # Configure _get_newest_db_statistic mock
        async def mock_newest_impl(hass: HomeAssistant, statistic_id: str) -> dict | None:
            if statistic_id not in entity_metadata:
                return None
            meta = entity_metadata[statistic_id]
            return {
                "start": meta["t_newest_db"],
                "sum": float(meta["newest_db_record"]["sum"]),
                "state": float(meta["newest_db_record"]["state"]),
            }

        mock_newest.side_effect = mock_newest_impl

        # Configure _get_reference_before_timestamp mock with call tracking
        call_counts: dict[str, int] = {}

        async def mock_before_impl(hass: HomeAssistant, statistic_id: str, timestamp: dt.datetime) -> dict | None:
            if statistic_id not in entity_metadata:
                return None

            if statistic_id not in call_counts:
                call_counts[statistic_id] = 0
            call_counts[statistic_id] += 1

            meta = entity_metadata[statistic_id]
            call_num = call_counts[statistic_id]

            if call_num == 1:
                # First call: returns t_oldest_import - 1 hour
                ref_time = meta["t_oldest_import"] - dt.timedelta(hours=1)
                if ref_time < meta["t_oldest_db"]:
                    return None
                # Find record at this time in DB
                matching_records = meta["db_entity"][meta["db_entity"]["datetime"] == ref_time.replace(tzinfo=None)]
                if len(matching_records) > 0:
                    rec = matching_records.iloc[0]
                    return {
                        "start": ref_time,
                        "sum": float(rec["sum"]),
                        "state": float(rec["state"]),
                    }
                return None
            else:
                # Second call: returns t_newest_import - 1 hour
                ref_time = meta["t_newest_import"] - dt.timedelta(hours=1)
                # Check if ref_time <= oldest in DB
                if ref_time <= meta["t_oldest_db"]:
                    return None
                # Find record at this time in DB
                matching_records = meta["db_entity"][meta["db_entity"]["datetime"] == ref_time.replace(tzinfo=None)]
                if len(matching_records) > 0:
                    rec = matching_records.iloc[0]
                    return {
                        "start": ref_time,
                        "sum": float(rec["sum"]),
                        "state": float(rec["state"]),
                    }
                return None

        mock_before.side_effect = mock_before_impl

        # Configure _get_reference_at_or_after_timestamp mock
        async def mock_after_impl(hass: HomeAssistant, statistic_id: str, timestamp: dt.datetime) -> dict | None:
            if statistic_id not in entity_metadata:
                return None

            meta = entity_metadata[statistic_id]
            # Returns value at t_newest_import. If t_newest_import > newest in DB, return None
            if meta["t_newest_import"] > meta["t_newest_db"]:
                return None
            # Find record at t_newest_import
            matching_records = meta["db_entity"][meta["db_entity"]["datetime"] == meta["t_newest_import"].replace(tzinfo=None)]
            if len(matching_records) > 0:
                rec = matching_records.iloc[0]
                return {
                    "start": meta["t_newest_import"],
                    "sum": float(rec["sum"]),
                    "state": float(rec["state"]),
                }
            return None

        mock_after.side_effect = mock_after_impl

    @staticmethod
    def _collect_import_calls(mock_import: MagicMock, mock_import_ext: MagicMock) -> dict:
        """Collect import calls from both internal and external import functions."""
        calls_by_id = {}

        for call_obj in mock_import.call_args_list:
            metadata = call_obj[0][1]
            statistics = call_obj[0][2]
            calls_by_id[metadata["statistic_id"]] = (metadata, statistics)

        for call_obj in mock_import_ext.call_args_list:
            metadata = call_obj[0][1]
            statistics = call_obj[0][2]
            calls_by_id[metadata["statistic_id"]] = (metadata, statistics)

        return calls_by_id

    @staticmethod
    def _verify_all_statistics(calls_by_id: dict, expected_df: pd.DataFrame) -> None:
        """Verify all statistic values match expected output.

        The expected_df contains all rows from the expected file, including reference rows.
        We only verify the rows that were actually imported (based on the first imported row timestamp).
        """
        for entity_id in expected_df["statistic_id"].unique():
            assert entity_id in calls_by_id, f"Entity {entity_id} not found in import calls"

            metadata, stats = calls_by_id[entity_id]
            expected_entity = expected_df[expected_df["statistic_id"] == entity_id]

            # Find which rows in expected_entity were actually imported
            # by matching the first imported statistic timestamp
            expected_entity_to_verify = expected_entity
            if len(stats) > 0:
                first_stat_start = stats[0]["start"]
                # Convert datetime to string format matching expected data
                first_stat_str = first_stat_start.strftime("%d.%m.%Y %H:%M")
                matching_rows = expected_entity[expected_entity["start"] == first_stat_str]

                if len(matching_rows) > 0:
                    # Start from the first matching row
                    start_idx = expected_entity.index.get_loc(matching_rows.index[0])
                    expected_entity_to_verify = expected_entity.iloc[start_idx:]

            # Verify all statistics for this entity match expected
            assert len(stats) == len(expected_entity_to_verify), \
                f"Expected {len(expected_entity_to_verify)} stats for {entity_id}, got {len(stats)}"

            for i, stat in enumerate(stats):
                expected_stat = expected_entity_to_verify.iloc[i]
                expected_timestamp_str = expected_stat["start"]
                expected_timestamp = pd.to_datetime(expected_timestamp_str, format="%d.%m.%Y %H:%M")

                assert stat["start"].year == expected_timestamp.year
                assert stat["start"].month == expected_timestamp.month
                assert stat["start"].day == expected_timestamp.day
                assert stat["start"].hour == expected_timestamp.hour
                assert stat["start"].minute == expected_timestamp.minute

                if not pd.isna(expected_stat.get("sum")):
                    assert pytest.approx(stat["sum"]) == pytest.approx(float(expected_stat["sum"])), \
                        f"Sum mismatch for {entity_id} at {stat['start']}: expected {expected_stat['sum']}, got {stat['sum']}"
                if not pd.isna(expected_stat.get("state")):
                    assert pytest.approx(stat["state"]) == pytest.approx(float(expected_stat["state"])), \
                        f"State mismatch for {entity_id} at {stat['start']}: expected {expected_stat['state']}, got {stat['state']}"
