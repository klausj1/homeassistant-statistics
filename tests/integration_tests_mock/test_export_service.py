"""Unit tests for HA-dependent export functions."""

import datetime
import tempfile
import zoneinfo
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics import setup
from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_END_TIME,
    ATTR_ENTITIES,
    ATTR_FILENAME,
    ATTR_START_TIME,
    ATTR_TIMEZONE_IDENTIFIER,
)
from custom_components.import_statistics.export_service import get_statistics_from_recorder
from tests.conftest import mock_async_add_executor_job

# Test constants
EXPECTED_RESULT_TUPLE_LENGTH = 2
EXPECTED_EXECUTOR_JOB_CALLS = 2


class TestGetStatisticsFromRecorder:
    """Test get_statistics_from_recorder function."""

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_valid(self) -> None:
        """Test fetching statistics with valid parameters."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        mock_statistics = {
            "sensor.temperature": [
                {
                    "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                    "end": datetime.datetime(2024, 1, 26, 13, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                    "mean": 20.5,
                    "min": 20.0,
                    "max": 21.0,
                }
            ]
        }

        mock_metadata = {"sensor.temperature": (1, {"unit_of_measurement": "°C"})}

        mock_recorder = MagicMock()
        # Side effect returns metadata on first call, statistics on second call
        mock_recorder.async_add_executor_job = AsyncMock(side_effect=[mock_metadata, mock_statistics])

        with patch("custom_components.import_statistics.export_service.get_instance") as mock_get_instance:
            mock_get_instance.return_value = mock_recorder

            result = await get_statistics_from_recorder(hass, ["sensor.temperature"], "2024-01-26 12:00:00", "2024-01-26 13:00:00")

            # Result should be tuple: (statistics_dict, units_dict)
            assert isinstance(result, tuple)
            assert len(result) == EXPECTED_RESULT_TUPLE_LENGTH
            stats_dict, units_dict = result
            assert stats_dict == mock_statistics
            assert "sensor.temperature" in stats_dict
            assert isinstance(stats_dict["sensor.temperature"], list)
            assert stats_dict["sensor.temperature"] == mock_statistics["sensor.temperature"]
            assert isinstance(units_dict, dict)
            assert units_dict["sensor.temperature"] == "°C"
            assert mock_recorder.async_add_executor_job.call_count == EXPECTED_EXECUTOR_JOB_CALLS

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_uses_db_range_when_times_omitted(self) -> None:
        """Test that missing start/end times are resolved from DB range."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        mock_statistics = {
            "sensor.temperature": [
                {
                    "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                    "mean": 20.5,
                }
            ]
        }
        mock_metadata = {"sensor.temperature": (1, {"unit_of_measurement": "°C"})}

        mock_recorder = MagicMock()
        mock_recorder.async_add_executor_job = AsyncMock(side_effect=[mock_metadata, mock_statistics])

        db_start = datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
        db_end = datetime.datetime(2024, 1, 26, 13, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))

        with (
            patch("custom_components.import_statistics.export_service.get_instance") as mock_get_instance,
            patch("custom_components.import_statistics.export_service.get_global_statistics_time_range", new_callable=AsyncMock) as mock_get_range,
        ):
            mock_get_instance.return_value = mock_recorder
            mock_get_range.return_value = (db_start, db_end)

            stats_dict, units_dict = await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                None,
                None,
            )

            assert stats_dict == mock_statistics
            assert units_dict["sensor.temperature"] == "°C"
            mock_get_range.assert_awaited_once()
            assert mock_recorder.async_add_executor_job.call_count == EXPECTED_EXECUTOR_JOB_CALLS

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_with_timezone(self) -> None:
        """Test that start/end times are interpreted in the provided timezone."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        mock_metadata = {"sensor.temperature": (1, {"unit_of_measurement": "°C"})}
        mock_statistics = {
            "sensor.temperature": [
                {
                    "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                    "mean": 20.5,
                }
            ]
        }

        mock_recorder = MagicMock()
        # Side effect returns metadata on first call, statistics on second call
        mock_recorder.async_add_executor_job = AsyncMock(side_effect=[mock_metadata, mock_statistics])

        with patch("custom_components.import_statistics.export_service.get_instance") as mock_get_instance:
            mock_get_instance.return_value = mock_recorder

            # User provides times in Europe/Vienna timezone
            # 2024-01-26 12:00:00 Vienna = 2024-01-26 11:00:00 UTC
            result = await get_statistics_from_recorder(hass, ["sensor.temperature"], "2024-01-26 12:00:00", "2024-01-26 13:00:00", "Europe/Vienna")

            # Verify async_add_executor_job was called
            assert mock_recorder.async_add_executor_job.call_count == EXPECTED_EXECUTOR_JOB_CALLS
            stats_dict, _units_dict = result
            assert stats_dict == mock_statistics

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_invalid_start_time_format(self) -> None:
        """Test error handling with invalid start time format."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="Invalid datetime format"):
            await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00",  # Missing seconds
                "2024-01-26 13:00:00",
            )

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_invalid_end_time_format(self) -> None:
        """Test error handling with invalid end time format."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="Invalid datetime format"):
            await get_statistics_from_recorder(hass, ["sensor.temperature"], "2024-01-26 12:00:00", "not-a-datetime")

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_start_time_not_full_hour(self) -> None:
        """Test error when start time is not a full hour."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="start_time must be a full hour"):
            await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:30:00",  # Not a full hour
                "2024-01-26 13:00:00",
            )

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_end_time_not_full_hour(self) -> None:
        """Test error when end time is not a full hour."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="end_time must be a full hour"):
            await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:45",  # Has seconds
            )

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_recorder_not_running(self) -> None:
        """Test error when recorder component is not running."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with patch("custom_components.import_statistics.export_service.get_instance") as mock_get_instance:
            mock_get_instance.return_value = None

            with pytest.raises(HomeAssistantError, match="Recorder component is not running"):
                await get_statistics_from_recorder(hass, ["sensor.temperature"], "2024-01-26 12:00:00", "2024-01-26 13:00:00")

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_multiple_entities(self) -> None:
        """Test fetching statistics for multiple entities."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        mock_metadata = {"sensor.temperature": (1, {"unit_of_measurement": "°C"}), "sensor.humidity": (2, {"unit_of_measurement": "%"})}
        mock_statistics = {"sensor.temperature": [{"mean": 20.5}], "sensor.humidity": [{"mean": 65.0}]}

        mock_recorder = MagicMock()
        # Side effect returns metadata on first call, statistics on second call
        mock_recorder.async_add_executor_job = AsyncMock(side_effect=[mock_metadata, mock_statistics])

        with patch("custom_components.import_statistics.export_service.get_instance") as mock_get_instance:
            mock_get_instance.return_value = mock_recorder

            result = await get_statistics_from_recorder(hass, ["sensor.temperature", "sensor.humidity"], "2024-01-26 12:00:00", "2024-01-26 13:00:00")

            assert len(result) == EXPECTED_RESULT_TUPLE_LENGTH
            stats_dict, _units_dict = result
            assert "sensor.temperature" in stats_dict
            assert "sensor.humidity" in stats_dict

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_external_statistic_id(self) -> None:
        """Test fetching statistics with external statistic ID (colon format)."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        mock_metadata = {"custom:my_metric": (1, {"unit_of_measurement": None})}
        mock_statistics = {"custom:my_metric": [{"mean": 100.0}]}

        mock_recorder = MagicMock()
        # Side effect returns metadata on first call, statistics on second call
        mock_recorder.async_add_executor_job = AsyncMock(side_effect=[mock_metadata, mock_statistics])

        with patch("custom_components.import_statistics.export_service.get_instance") as mock_get_instance:
            mock_get_instance.return_value = mock_recorder

            result = await get_statistics_from_recorder(hass, ["custom:my_metric"], "2024-01-26 12:00:00", "2024-01-26 13:00:00")

            stats_dict, _units_dict = result
            assert "custom:my_metric" in stats_dict

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_invalid_entity_id(self) -> None:
        """Test error with invalid entity ID format."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="invalid"):
            await get_statistics_from_recorder(hass, ["invalid_entity_id_no_separator"], "2024-01-26 12:00:00", "2024-01-26 13:00:00")

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_calls_recorder_api(self) -> None:
        """Test that recorder API is called with correct parameters."""
        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        mock_metadata = {}
        mock_statistics = {}

        mock_recorder = MagicMock()
        # Side effect returns metadata on first call, statistics on second call
        mock_recorder.async_add_executor_job = AsyncMock(side_effect=[mock_metadata, mock_statistics])

        with patch("custom_components.import_statistics.export_service.get_instance") as mock_get_instance:
            mock_get_instance.return_value = mock_recorder

            await get_statistics_from_recorder(hass, ["sensor.temperature"], "2024-01-26 12:00:00", "2024-01-26 13:00:00")

            # Verify async_add_executor_job was called twice
            assert mock_recorder.async_add_executor_job.call_count == EXPECTED_EXECUTOR_JOB_CALLS

            # Check first call (metadata)
            first_call_args = mock_recorder.async_add_executor_job.call_args_list[0]
            assert callable(first_call_args[0][0])  # First arg should be a function

            # Check second call (statistics)
            second_call_args = mock_recorder.async_add_executor_job.call_args_list[1]
            assert callable(second_call_args[0][0])  # First arg should be a function


class TestHandleExportStatistics:
    """Test handle_export_statistics service handler."""

    @pytest.mark.asyncio
    async def test_handle_export_statistics_valid_call(self) -> None:
        """Test successful export with valid parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: False,
                    ATTR_DATETIME_FORMAT: "%d.%m.%Y %H:%M",
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file"),
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify state was set
                hass.states.async_set.assert_called_with("import_statistics.export_statistics", "OK")

    @pytest.mark.asyncio
    async def test_handle_export_statistics_without_time_range(self) -> None:
        """Test successful export without specifying start_time/end_time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file"),
            ):
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                hass.states.async_set.assert_called_with("import_statistics.export_statistics", "OK")

    @pytest.mark.asyncio
    async def test_handle_export_statistics_with_defaults(self) -> None:
        """Test export with default parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file"),
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify defaults were used
                assert mock_get_stats.called

    @pytest.mark.asyncio
    async def test_handle_export_statistics_invalid_timezone(self) -> None:
        """Test error handling with invalid timezone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "Invalid/Timezone",
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                error_msg = "Invalid timezone_identifier"

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    raise HomeAssistantError(error_msg)

                mock_get_stats.side_effect = async_mock

                with pytest.raises(HomeAssistantError):
                    await service_handler(call)

    @pytest.mark.asyncio
    async def test_handle_export_statistics_recorder_not_running(self) -> None:
        """Test error when recorder is not running."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                error_msg = "Recorder component is not running"

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    raise HomeAssistantError(error_msg)

                mock_get_stats.side_effect = async_mock

                with pytest.raises(HomeAssistantError):
                    await service_handler(call)

    @pytest.mark.asyncio
    async def test_handle_export_statistics_file_path_construction(self) -> None:
        """Test that file path is constructed correctly from config_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file") as mock_write,
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify file path was constructed correctly
                call_args = mock_write.call_args
                assert call_args[0][0] == f"{tmpdir}/export.tsv"

    @pytest.mark.asyncio
    async def test_handle_export_statistics_with_csv_delimiter(self) -> None:
        """Test export with CSV comma delimiter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.csv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                    ATTR_DELIMITER: ",",
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file") as mock_write,
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify delimiter was passed correctly
                call_args = mock_write.call_args
                assert call_args[0][3] == ","

    @pytest.mark.asyncio
    async def test_handle_export_statistics_multiple_entities(self) -> None:
        """Test export with multiple entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ],
                "sensor.humidity": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 65.0,
                        "min": 60.0,
                        "max": 70.0,
                    }
                ],
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature", "sensor.humidity"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file"),
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C", "sensor.humidity": "%"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify both entities were processed
                assert mock_get_stats.called

    @pytest.mark.asyncio
    async def test_handle_export_statistics_timezone_parameter(self) -> None:
        """Test that timezone parameter is passed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "Europe/Vienna",
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file"),
                patch("custom_components.import_statistics.export_service.prepare_export_data") as mock_prepare,
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                mock_prepare.return_value = (["col1"], [("row1",)])

                await service_handler(call)

                # Verify timezone was passed to prepare_export_data
                call_args = mock_prepare.call_args
                assert call_args[0][1] == "Europe/Vienna"

    @pytest.mark.asyncio
    async def test_handle_export_statistics_decimal_comma(self) -> None:
        """Test export with comma decimal separator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                    ATTR_DECIMAL: True,
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file"),
                patch("custom_components.import_statistics.export_service.prepare_export_data") as mock_prepare,
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                mock_prepare.return_value = (["col1"], [("row1",)])

                await service_handler(call)

                # Verify decimal parameter was passed
                call_args = mock_prepare.call_args
                assert call_args[1]["decimal_comma"] is True

    @pytest.mark.asyncio
    async def test_handle_export_statistics_datetime_format(self) -> None:
        """Test export with custom datetime format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                    ATTR_DATETIME_FORMAT: "%Y-%m-%d %H:%M",
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file"),
                patch("custom_components.import_statistics.export_service.prepare_export_data") as mock_prepare,
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                mock_prepare.return_value = (["col1"], [("row1",)])

                await service_handler(call)

                # Verify datetime format was passed
                call_args = mock_prepare.call_args
                assert call_args[0][2] == "%Y-%m-%d %H:%M"

    @pytest.mark.asyncio
    async def test_handle_export_statistics_sets_ok_state(self) -> None:
        """Test that state is set to OK on successful export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file"),
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify state was set to OK
                hass.states.async_set.assert_called_with("import_statistics.export_statistics", "OK")

    @pytest.mark.asyncio
    async def test_handle_export_statistics_error_propagates(self) -> None:
        """Test that errors from write are propagated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 13:00:00",
                },
            )

            with (
                patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats,
                patch("custom_components.import_statistics.export_service.write_export_file") as mock_write,
            ):
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}

                async def async_mock(*_args: Any, **_kwargs: Any) -> tuple[dict, dict]:
                    return (mock_statistics, mock_units)

                mock_get_stats.side_effect = async_mock
                mock_write.side_effect = HomeAssistantError("Permission denied")

                with pytest.raises(HomeAssistantError, match="Permission denied"):
                    await service_handler(call)
