"""Unit tests for HA-dependent export functions."""

import datetime
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

    def test_get_statistics_from_recorder_valid(self) -> None:
        """Test fetching statistics with valid parameters."""
        from custom_components.import_statistics import get_statistics_from_recorder

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

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance, \
             patch("custom_components.import_statistics.statistics_during_period") as mock_stats_during:
            mock_get_instance.return_value = MagicMock()
            mock_stats_during.return_value = mock_statistics

            result = get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

            # Result should be raw format from recorder API
            assert result == mock_statistics
            assert "sensor.temperature" in result
            assert isinstance(result["sensor.temperature"], list)
            assert result["sensor.temperature"] == mock_statistics["sensor.temperature"]
            mock_stats_during.assert_called_once()

    def test_get_statistics_from_recorder_invalid_start_time_format(self) -> None:
        """Test error handling with invalid start time format."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        with pytest.raises(HomeAssistantError, match="Invalid datetime format"):
            get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00",  # Missing seconds
                "2024-01-26 13:00:00"
            )

    def test_get_statistics_from_recorder_invalid_end_time_format(self) -> None:
        """Test error handling with invalid end time format."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        with pytest.raises(HomeAssistantError, match="Invalid datetime format"):
            get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "not-a-datetime"
            )

    def test_get_statistics_from_recorder_start_time_not_full_hour(self) -> None:
        """Test error when start time is not a full hour."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        with pytest.raises(HomeAssistantError, match="start_time must be a full hour"):
            get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:30:00",  # Not a full hour
                "2024-01-26 13:00:00"
            )

    def test_get_statistics_from_recorder_end_time_not_full_hour(self) -> None:
        """Test error when end time is not a full hour."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        with pytest.raises(HomeAssistantError, match="end_time must be a full hour"):
            get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:45"  # Has seconds
            )

    def test_get_statistics_from_recorder_recorder_not_running(self) -> None:
        """Test error when recorder component is not running."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance:
            mock_get_instance.return_value = None

            with pytest.raises(HomeAssistantError, match="Recorder component is not running"):
                get_statistics_from_recorder(
                    hass,
                    ["sensor.temperature"],
                    "2024-01-26 12:00:00",
                    "2024-01-26 13:00:00"
                )

    def test_get_statistics_from_recorder_multiple_entities(self) -> None:
        """Test fetching statistics for multiple entities."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        mock_statistics = {
            "sensor.temperature": [{"mean": 20.5}],
            "sensor.humidity": [{"mean": 65.0}]
        }

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance, \
             patch("custom_components.import_statistics.statistics_during_period") as mock_stats_during:
            mock_get_instance.return_value = MagicMock()
            mock_stats_during.return_value = mock_statistics

            result = get_statistics_from_recorder(
                hass,
                ["sensor.temperature", "sensor.humidity"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

            assert len(result) == 2
            assert "sensor.temperature" in result
            assert "sensor.humidity" in result

    def test_get_statistics_from_recorder_external_statistic_id(self) -> None:
        """Test fetching statistics with external statistic ID (colon format)."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        mock_statistics = {
            "custom:my_metric": [{"mean": 100.0}]
        }

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance, \
             patch("custom_components.import_statistics.statistics_during_period") as mock_stats_during:
            mock_get_instance.return_value = MagicMock()
            mock_stats_during.return_value = mock_statistics

            result = get_statistics_from_recorder(
                hass,
                ["custom:my_metric"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

            assert "custom:my_metric" in result

    def test_get_statistics_from_recorder_invalid_entity_id(self) -> None:
        """Test error with invalid entity ID format."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        with pytest.raises(HomeAssistantError, match="invalid"):
            get_statistics_from_recorder(
                hass,
                ["invalid_entity_id_no_separator"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

    def test_get_statistics_from_recorder_calls_recorder_api(self) -> None:
        """Test that recorder API is called with correct parameters."""
        from custom_components.import_statistics import get_statistics_from_recorder

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

        with patch("custom_components.import_statistics.get_instance") as mock_get_instance, \
             patch("custom_components.import_statistics.statistics_during_period") as mock_stats_during:
            mock_get_instance.return_value = MagicMock()
            mock_stats_during.return_value = {}

            get_statistics_from_recorder(
                hass,
                ["sensor.temperature"],
                "2024-01-26 12:00:00",
                "2024-01-26 13:00:00"
            )

            # Verify recorder API was called
            assert mock_stats_during.called
            args, kwargs = mock_stats_during.call_args

            # Check parameters
            assert args[0] == hass
            assert isinstance(args[1], datetime.datetime)
            assert isinstance(args[2], datetime.datetime)
            assert "sensor.temperature" in args[3]
            assert args[4] == "hour"  # period
            assert args[5] is None  # units
            assert set(args[6]) == {"max", "mean", "min", "state", "sum"}  # types


class TestHandleExportStatistics:
    """Test handle_export_statistics service handler."""

    def test_handle_export_statistics_valid_call(self) -> None:
        """Test successful export with valid parameters."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics

            service_handler(call)

            # Verify write was called
            mock_write.assert_called_once()

            # Verify state was set
            hass.states.set.assert_called_with("import_statistics.export_statistics", "OK")

    def test_handle_export_statistics_with_defaults(self) -> None:
        """Test export with default parameters."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics

            service_handler(call)

            # Verify defaults were used
            assert mock_get_stats.called
            assert mock_write.called

    def test_handle_export_statistics_invalid_timezone(self) -> None:
        """Test error handling with invalid timezone."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.side_effect = HomeAssistantError("Invalid timezone_identifier")

            with pytest.raises(HomeAssistantError):
                service_handler(call)

    def test_handle_export_statistics_recorder_not_running(self) -> None:
        """Test error when recorder is not running."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.side_effect = HomeAssistantError("Recorder component is not running")

            with pytest.raises(HomeAssistantError):
                service_handler(call)

    def test_handle_export_statistics_file_path_construction(self) -> None:
        """Test that file path is constructed correctly from config_dir."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics

            service_handler(call)

            # Verify file path was constructed correctly
            call_args = mock_write.call_args
            assert call_args[0][0] == "/config/export.tsv"

    def test_handle_export_statistics_with_csv_delimiter(self) -> None:
        """Test export with CSV comma delimiter."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics

            service_handler(call)

            # Verify delimiter was passed correctly
            call_args = mock_write.call_args
            assert call_args[0][3] == ","

    def test_handle_export_statistics_multiple_entities(self) -> None:
        """Test export with multiple entities."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics

            service_handler(call)

            # Verify both entities were processed
            assert mock_get_stats.called
            assert mock_write.called

    def test_handle_export_statistics_timezone_parameter(self) -> None:
        """Test that timezone parameter is passed correctly."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics
            mock_prepare.return_value = (["col1"], [("row1",)])

            service_handler(call)

            # Verify timezone was passed to prepare_export_data
            call_args = mock_prepare.call_args
            assert call_args[0][1] == "Europe/Vienna"

    def test_handle_export_statistics_decimal_comma(self) -> None:
        """Test export with comma decimal separator."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics
            mock_prepare.return_value = (["col1"], [("row1",)])

            service_handler(call)

            # Verify decimal parameter was passed
            call_args = mock_prepare.call_args
            assert call_args[0][4] is True

    def test_handle_export_statistics_datetime_format(self) -> None:
        """Test export with custom datetime format."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics
            mock_prepare.return_value = (["col1"], [("row1",)])

            service_handler(call)

            # Verify datetime format was passed
            call_args = mock_prepare.call_args
            assert call_args[0][2] == "%Y-%m-%d %H:%M"

    def test_handle_export_statistics_sets_ok_state(self) -> None:
        """Test that state is set to OK on successful export."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics

            service_handler(call)

            # Verify state was set to OK
            hass.states.set.assert_called_with("import_statistics.export_statistics", "OK")

    def test_handle_export_statistics_error_propagates(self) -> None:
        """Test that errors from write are propagated."""
        from custom_components.import_statistics import setup

        hass = MagicMock()
        hass.config = MagicMock()
        hass.config.config_dir = "/config"

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
            mock_get_stats.return_value = mock_statistics
            mock_write.side_effect = HomeAssistantError("Permission denied")

            with pytest.raises(HomeAssistantError, match="Permission denied"):
                service_handler(call)
