"""Unit tests for HA-dependent export functions."""

import datetime
import tempfile
import zoneinfo
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.const import (
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_END_TIME,
    ATTR_ENTITIES,
    ATTR_FILENAME,
    ATTR_START_TIME,
    ATTR_TIMEZONE_IDENTIFIER,
    DATETIME_DEFAULT_FORMAT,
    DATETIME_INPUT_FORMAT,
)


class TestGetStatisticsFromRecorder:
    """Test get_statistics_from_recorder function."""

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_valid(self) -> None:
        """Test fetching statistics with valid parameters."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

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

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance:
            mock_get_instance.return_value = MagicMock()
            # Mock async_add_executor_job to return the statistics directly
            hass.async_add_executor_job.return_value = mock_statistics

            result = await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

            # Result should be tuple: (statistics_dict, units_dict)
            assert isinstance(result, tuple)
            assert len(result) == 2
            stats_dict, units_dict = result
            assert stats_dict == mock_statistics
            assert "sensor.temperature" in stats_dict
            assert isinstance(stats_dict["sensor.temperature"], list)
            assert stats_dict["sensor.temperature"] == mock_statistics["sensor.temperature"]
            assert isinstance(units_dict, dict)
            hass.async_add_executor_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_with_timezone(self) -> None:
        """Test that start/end times are interpreted in the provided timezone."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        mock_statistics = {
            "sensor.temperature": [
                {
                    "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                    "mean": 20.5,
                }
            ]
        }

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance:
            mock_get_instance.return_value = MagicMock()
            hass.async_add_executor_job.return_value = mock_statistics

            # User provides times in Europe/Vienna timezone
            # 2024-01-26 12:00:00 Vienna = 2024-01-26 11:00:00 UTC
            result = await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00",
                "Europe/Vienna"
            )

            # Verify async_add_executor_job was called
            hass.async_add_executor_job.assert_called_once()
            call_args = hass.async_add_executor_job.call_args
            # Verify the executor was called with the right time boundaries
            # start_dt should be 11:00:00 UTC (12:00:00 Vienna - 1 hour)
            assert call_args[0][2].hour == 11
            # end_dt should be 13:00:00 UTC (14:00:00 Vienna, plus 1 hour buffer)
            assert call_args[0][3].hour == 13
            stats_dict, units_dict = result
            assert stats_dict == mock_statistics

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_invalid_start_time_format(self) -> None:
        """Test error handling with invalid start time format."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="Invalid datetime format"):
            await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00",  # Missing seconds
                "2024-01-26 13:00:00"
            )

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_invalid_end_time_format(self) -> None:
        """Test error handling with invalid end time format."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="Invalid datetime format"):
            await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "not-a-datetime"
            )

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_start_time_not_full_hour(self) -> None:
        """Test error when start time is not a full hour."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="start_time must be a full hour"):
            await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:30:00",  # Not a full hour
                "2024-01-26 13:00:00"
            )

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_end_time_not_full_hour(self) -> None:
        """Test error when end time is not a full hour."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="end_time must be a full hour"):
            await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:45"  # Has seconds
            )

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_recorder_not_running(self) -> None:
        """Test error when recorder component is not running."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance:
            mock_get_instance.return_value = None

            with pytest.raises(HomeAssistantError, match="Recorder component is not running"):
                await get_statistics_from_recorder(
                    hass,
                    ["sensor.temperature"],
                    "2024-01-26 12:00:00",
                    "2024-01-26 13:00:00"
                )

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_multiple_entities(self) -> None:
        """Test fetching statistics for multiple entities."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        mock_statistics = {
            "sensor.temperature": [{"mean": 20.5}],
            "sensor.humidity": [{"mean": 65.0}]
        }

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance:
            mock_get_instance.return_value = MagicMock()
            hass.async_add_executor_job.return_value = mock_statistics

            result = await get_statistics_from_recorder(
                hass,
                ["sensor.temperature", "sensor.humidity"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

            assert len(result) == 2
            stats_dict, units_dict = result
            assert "sensor.temperature" in stats_dict
            assert "sensor.humidity" in stats_dict

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_external_statistic_id(self) -> None:
        """Test fetching statistics with external statistic ID (colon format)."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        mock_statistics = {
            "custom:my_metric": [{"mean": 100.0}]
        }

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance:
            mock_get_instance.return_value = MagicMock()
            hass.async_add_executor_job.return_value = mock_statistics

            result = await get_statistics_from_recorder(
                hass,
                ["custom:my_metric"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

            stats_dict, units_dict = result
            assert "custom:my_metric" in stats_dict

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_invalid_entity_id(self) -> None:
        """Test error with invalid entity ID format."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with pytest.raises(HomeAssistantError, match="invalid"):
            await get_statistics_from_recorder(
                hass,
                ["invalid_entity_id_no_separator"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

    @pytest.mark.asyncio
    async def test_get_statistics_from_recorder_calls_recorder_api(self) -> None:
        """Test that recorder API is called with correct parameters."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"
        hass.async_add_executor_job = AsyncMock()

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance:
            mock_get_instance.return_value = MagicMock()
            hass.async_add_executor_job.return_value = {}

            await get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

            # Verify async_add_executor_job was called
            assert hass.async_add_executor_job.called
            args, kwargs = hass.async_add_executor_job.call_args

            # Check parameters passed to executor
            # args[0] is the function, args[1:] are the arguments
            assert args[1] == hass
            assert isinstance(args[2], datetime.datetime)
            assert isinstance(args[3], datetime.datetime)
            assert "sensor.temperature" in args[4]
            assert args[5] == "hour"  # period
            assert args[6] is None  # units
            assert set(args[7]) == {"max", "mean", "min", "state", "sum"}  # types


class TestHandleExportStatistics:
    """Test handle_export_statistics service handler."""

    @pytest.mark.asyncio
    async def test_handle_export_statistics_valid_call(self) -> None:
        """Test successful export with valid parameters."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                # Make the mock return an async function result
                async def async_mock(*args, **kwargs):
                    return (mock_statistics, mock_units)
                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify write was called
                mock_write.assert_called_once()

                # Verify state was set
                hass.states.async_set.assert_called_with("import_statistics.export_statistics", "OK")

    @pytest.mark.asyncio
    async def test_handle_export_statistics_with_defaults(self) -> None:
        """Test export with default parameters."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                async def async_mock(*args, **kwargs):
                    return (mock_statistics, mock_units)
                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify defaults were used
                assert mock_get_stats.called
                assert mock_write.called

    @pytest.mark.asyncio
    async def test_handle_export_statistics_invalid_timezone(self) -> None:
        """Test error handling with invalid timezone."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                async def async_mock(*args, **kwargs):
                    raise HomeAssistantError("Invalid timezone_identifier")
                mock_get_stats.side_effect = async_mock

                with pytest.raises(HomeAssistantError):
                    await service_handler(call)

    @pytest.mark.asyncio
    async def test_handle_export_statistics_recorder_not_running(self) -> None:
        """Test error when recorder is not running."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                async def async_mock(*args, **kwargs):
                    raise HomeAssistantError("Recorder component is not running")
                mock_get_stats.side_effect = async_mock

                with pytest.raises(HomeAssistantError):
                    await service_handler(call)

    @pytest.mark.asyncio
    async def test_handle_export_statistics_file_path_construction(self) -> None:
        """Test that file path is constructed correctly from config_dir."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                async def async_mock(*args, **kwargs):
                    return (mock_statistics, mock_units)
                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify file path was constructed correctly
                call_args = mock_write.call_args
                assert call_args[0][0] == f"{tmpdir}/export.tsv"

    @pytest.mark.asyncio
    async def test_handle_export_statistics_with_csv_delimiter(self) -> None:
        """Test export with CSV comma delimiter."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                async def async_mock(*args, **kwargs):
                    return (mock_statistics, mock_units)
                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify delimiter was passed correctly
                call_args = mock_write.call_args
                assert call_args[0][3] == ","

    @pytest.mark.asyncio
    async def test_handle_export_statistics_multiple_entities(self) -> None:
        """Test export with multiple entities."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                ]
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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {
                    "sensor.temperature": "°C",
                    "sensor.humidity": "%"
                }
                async def async_mock(*args, **kwargs):
                    return (mock_statistics, mock_units)
                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify both entities were processed
                assert mock_get_stats.called
                assert mock_write.called

    @pytest.mark.asyncio
    async def test_handle_export_statistics_timezone_parameter(self) -> None:
        """Test that timezone parameter is passed correctly."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write, \
                 patch("custom_components.import_statistics.prepare_data.prepare_export_data") as mock_prepare:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                async def async_mock(*args, **kwargs):
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
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write, \
                 patch("custom_components.import_statistics.prepare_data.prepare_export_data") as mock_prepare:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                async def async_mock(*args, **kwargs):
                    return (mock_statistics, mock_units)
                mock_get_stats.side_effect = async_mock
                mock_prepare.return_value = (["col1"], [("row1",)])

                await service_handler(call)

                # Verify decimal parameter was passed
                call_args = mock_prepare.call_args
                assert call_args[0][4] is True

    @pytest.mark.asyncio
    async def test_handle_export_statistics_datetime_format(self) -> None:
        """Test export with custom datetime format."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write, \
                 patch("custom_components.import_statistics.prepare_data.prepare_export_data") as mock_prepare:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                async def async_mock(*args, **kwargs):
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
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                async def async_mock(*args, **kwargs):
                    return (mock_statistics, mock_units)
                mock_get_stats.side_effect = async_mock
                await service_handler(call)

                # Verify state was set to OK
                hass.states.async_set.assert_called_with("import_statistics.export_statistics", "OK")

    @pytest.mark.asyncio
    async def test_handle_export_statistics_error_propagates(self) -> None:
        """Test that errors from write are propagated."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir
            hass.async_add_executor_job = AsyncMock()

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
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats, \
                 patch("custom_components.import_statistics.prepare_data.write_export_file") as mock_write:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                async def async_mock(*args, **kwargs):
                    return (mock_statistics, mock_units)
                mock_get_stats.side_effect = async_mock
                mock_write.side_effect = HomeAssistantError("Permission denied")

                with pytest.raises(HomeAssistantError, match="Permission denied"):
                    await service_handler(call)
