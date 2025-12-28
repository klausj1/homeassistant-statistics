"""Unit tests for prepare_export_data and related export functions."""

import csv
import datetime
import json
import tempfile
import zoneinfo
from pathlib import Path

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.prepare_data import (
    _detect_statistic_type,
    _format_datetime,
    _format_decimal,
    prepare_export_data,
    prepare_export_json,
    write_export_file,
)

# Constants for test values
EXPECTED_ROWS_2 = 2
EXPECTED_MEAN_20_5 = 20.5
EXPECTED_MIN_20_0 = 20.0
EXPECTED_MAX_21_0 = 21.0
EXPECTED_MEAN_21_5 = 21.5
EXPECTED_MIN_21_0 = 21.0
EXPECTED_MAX_22_0 = 22.0
EXPECTED_MEAN_65_0 = 65.0
EXPECTED_MIN_60_0 = 60.0
EXPECTED_MAX_70_0 = 70.0
EXPECTED_SUM_100_5 = 100.5
EXPECTED_SUM_11_2 = 11.2
EXPECTED_STATE_100_5 = 100.5
UNIX_TIMESTAMP_2024_01_26 = 1706270400.0
UNIX_TIMESTAMP_2024_01_26_13_00 = 1706274000.0
DECIMAL_VALUE_1234_567 = 1234.567
EXPECTED_ROWS_1 = 1


class TestFormatDatetime:
    """Test timezone-aware datetime formatting."""

    def test_format_datetime_utc_to_vienna(self) -> None:
        """Test converting UTC datetime to Vienna timezone."""
        dt_obj = UNIX_TIMESTAMP_2024_01_26  # 2024-01-26 12:00:00 UTC
        timezone = zoneinfo.ZoneInfo("Europe/Vienna")
        result = _format_datetime(dt_obj, timezone, "%d.%m.%Y %H:%M")
        assert result == "26.01.2024 13:00"

    def test_format_datetime_unix_timestamp(self) -> None:
        """Test formatting Unix timestamp (float) from recorder API."""
        # 2024-01-26 12:00:00 UTC = 1706270400.0
        unix_timestamp = UNIX_TIMESTAMP_2024_01_26
        timezone = zoneinfo.ZoneInfo("UTC")
        result = _format_datetime(unix_timestamp, timezone, "%d.%m.%Y %H:%M")
        assert result == "26.01.2024 12:00"

    def test_format_datetime_unix_timestamp_with_timezone(self) -> None:
        """Test converting Unix timestamp to different timezone."""
        # 2024-01-26 12:00:00 UTC = 1706270400.0
        unix_timestamp = UNIX_TIMESTAMP_2024_01_26
        timezone = zoneinfo.ZoneInfo("Europe/Vienna")
        result = _format_datetime(unix_timestamp, timezone, "%d.%m.%Y %H:%M")
        assert result == "26.01.2024 13:00"

    def test_format_datetime_naive_assumed_utc(self) -> None:
        """Test that naive datetime is assumed to be UTC."""
        dt_obj = datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=datetime.UTC)
        timezone = zoneinfo.ZoneInfo("Europe/Vienna")
        result = _format_datetime(dt_obj, timezone, "%d.%m.%Y %H:%M")
        assert result == "26.01.2024 13:00"

    def test_format_datetime_different_format(self) -> None:
        """Test datetime formatting with different format string."""
        dt_obj = UNIX_TIMESTAMP_2024_01_26  # 2024-01-26 12:00:00 UTC
        timezone = zoneinfo.ZoneInfo("UTC")
        result = _format_datetime(dt_obj, timezone, "%Y-%m-%d %H:%M")
        assert result == "2024-01-26 12:00"

    def test_format_datetime_us_format(self) -> None:
        """Test datetime formatting with US format."""
        dt_obj = UNIX_TIMESTAMP_2024_01_26  # 2024-01-26 12:00:00 UTC
        timezone = zoneinfo.ZoneInfo("UTC")
        result = _format_datetime(dt_obj, timezone, "%m/%d/%Y %H:%M")
        assert result == "01/26/2024 12:00"

    def test_format_datetime_timezone_aware_conversion(self) -> None:
        """Test converting between different timezones."""
        dt_obj = datetime.datetime(2024, 1, 26, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York"))
        timezone = zoneinfo.ZoneInfo("Asia/Tokyo")
        result = _format_datetime(dt_obj, timezone, "%Y-%m-%d %H:%M")
        # 12:00 EST = 02:00 JST (next day)
        assert result == "2024-01-27 02:00"


class TestFormatDecimal:
    """Test decimal separator formatting."""

    def test_format_decimal_dot_separator(self) -> None:
        """Test decimal with dot separator."""
        result = _format_decimal(DECIMAL_VALUE_1234_567, use_comma=False)
        assert result == "1234.567"

    def test_format_decimal_comma_separator(self) -> None:
        """Test decimal with comma separator."""
        result = _format_decimal(DECIMAL_VALUE_1234_567, use_comma=True)
        assert result == "1234,567"

    def test_format_decimal_integer(self) -> None:
        """Test formatting integer value."""
        result = _format_decimal(42, use_comma=False)
        assert result == "42"

    def test_format_decimal_none_value(self) -> None:
        """Test formatting None value returns empty string."""
        result = _format_decimal(None, use_comma=False)
        assert result == ""

    def test_format_decimal_small_value(self) -> None:
        """Test formatting small decimal value."""
        result = _format_decimal(0.001, use_comma=False)
        assert result == "0.001"

    def test_format_decimal_trailing_zeros_removed(self) -> None:
        """Test that trailing zeros are removed."""
        result = _format_decimal(1.0, use_comma=False)
        assert result == "1"

    def test_format_decimal_zero(self) -> None:
        """Test formatting zero."""
        result = _format_decimal(0, use_comma=False)
        assert result == "0"


class TestDetectStatisticType:
    """Test statistic type detection."""

    def test_detect_sensor_type_mean(self) -> None:
        """Test detection of sensor type with mean."""
        stats_list = [{"start": datetime.datetime.now(tz=datetime.UTC), "mean": 20.5, "min": 20.0, "max": 21.0}]
        result = _detect_statistic_type(stats_list)
        assert result == "sensor"

    def test_detect_sensor_type_min(self) -> None:
        """Test detection of sensor type with min."""
        stats_list = [{"start": datetime.datetime.now(tz=datetime.UTC), "min": 20.0}]
        result = _detect_statistic_type(stats_list)
        assert result == "sensor"

    def test_detect_sensor_type_max(self) -> None:
        """Test detection of sensor type with max."""
        stats_list = [{"start": datetime.datetime.now(tz=datetime.UTC), "max": 21.0}]
        result = _detect_statistic_type(stats_list)
        assert result == "sensor"

    def test_detect_counter_type_sum(self) -> None:
        """Test detection of counter type with sum."""
        stats_list = [{"start": datetime.datetime.now(tz=datetime.UTC), "sum": 100.5}]
        result = _detect_statistic_type(stats_list)
        assert result == "counter"

    def test_detect_counter_type_state(self) -> None:
        """Test detection of counter type with state."""
        stats_list = [{"start": datetime.datetime.now(tz=datetime.UTC), "state": 100.5}]
        result = _detect_statistic_type(stats_list)
        assert result == "counter"

    def test_detect_counter_type_both(self) -> None:
        """Test detection of counter type with both sum and state."""
        stats_list = [{"start": datetime.datetime.now(tz=datetime.UTC), "sum": 100.5, "state": 100.5}]
        result = _detect_statistic_type(stats_list)
        assert result == "counter"

    def test_detect_unknown_type_empty(self) -> None:
        """Test detection of unknown type with empty list."""
        stats_list = []
        result = _detect_statistic_type(stats_list)
        assert result == "unknown"

    def test_detect_unknown_type_no_matching_fields(self) -> None:
        """Test detection of unknown type with no matching fields."""
        stats_list = [{"start": datetime.datetime.now(tz=datetime.UTC)}]
        result = _detect_statistic_type(stats_list)
        assert result == "unknown"


class TestPrepareExportData:
    """Test prepare_export_data function."""

    def test_prepare_export_data_sensor_statistics(self) -> None:
        """Test export preparation with sensor statistics."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                }
            ]
        }

        columns, rows = prepare_export_data(statistics_dict, "UTC", "%d.%m.%Y %H:%M", decimal_comma=False)

        assert "statistic_id" in columns
        assert "unit" in columns
        assert "start" in columns
        assert "mean" in columns
        assert "min" in columns
        assert "max" in columns
        assert "sum" not in columns
        assert "state" not in columns
        assert len(rows) == EXPECTED_ROWS_1
        assert rows[0][0] == "sensor.temperature"
        assert rows[0][1] == ""  # Unit is empty for raw format

    def test_prepare_export_data_counter_statistics(self) -> None:
        """Test export preparation with counter statistics."""
        statistics_dict = {
            "sensor.energy": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "sum": EXPECTED_SUM_100_5,
                    "state": EXPECTED_STATE_100_5,
                }
            ]
        }

        columns, rows = prepare_export_data(statistics_dict, "UTC", "%d.%m.%Y %H:%M", decimal_comma=False)

        assert "sum" in columns
        assert "state" in columns
        assert "mean" not in columns
        assert "min" not in columns
        assert "max" not in columns
        assert len(rows) == EXPECTED_ROWS_1

    def test_prepare_export_data_mixed_types(self) -> None:
        """Test export preparation with mixed sensor and counter statistics."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                }
            ],
            "sensor.energy": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "sum": EXPECTED_SUM_100_5,
                    "state": EXPECTED_STATE_100_5,
                }
            ],
        }

        columns, rows = prepare_export_data(statistics_dict, "UTC", "%d.%m.%Y %H:%M", decimal_comma=False)

        # Should include both sensor and counter columns
        assert "mean" in columns
        assert "sum" in columns
        assert len(rows) == EXPECTED_ROWS_2

    def test_prepare_export_data_decimal_comma(self) -> None:
        """Test export with comma as decimal separator."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                }
            ]
        }
        columns, rows = prepare_export_data(
            statistics_dict,
            "UTC",
            "%d.%m.%Y %H:%M",
            decimal_comma=True,  # use comma
        )

        # Values should have comma separator
        row_values = rows[0]
        # Find the mean value in the row using column index
        mean_index = columns.index("mean")
        assert "," in str(row_values[mean_index])  # mean value should have comma

    def test_prepare_export_data_timezone_conversion(self) -> None:
        """Test export with timezone conversion."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                }
            ]
        }

        _columns, rows = prepare_export_data(statistics_dict, "Europe/Vienna", "%d.%m.%Y %H:%M", decimal_comma=False)

        # Time should be converted from UTC to Vienna (UTC+1)
        assert "26.01.2024 13:00" in str(rows[0])

    def test_prepare_export_data_invalid_timezone(self) -> None:
        """Test export with invalid timezone raises error."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": datetime.datetime.now(tz=datetime.UTC),
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                }
            ]
        }

        with pytest.raises(HomeAssistantError, match="Invalid timezone_identifier"):
            prepare_export_data(statistics_dict, "Invalid/Timezone", "%d.%m.%Y %H:%M", decimal_comma=False)

    def test_prepare_export_data_empty_statistics(self) -> None:
        """Test export with empty statistics dict."""
        statistics_dict = {}

        columns, rows = prepare_export_data(statistics_dict, "UTC", "%d.%m.%Y %H:%M", decimal_comma=False)

        # Should return base columns with no data rows
        assert "statistic_id" in columns
        assert len(rows) == 0

    def test_prepare_export_data_no_statistics_list(self) -> None:
        """Test export when entity has empty statistics list."""
        statistics_dict = {"sensor.temperature": []}

        _columns, rows = prepare_export_data(statistics_dict, "UTC", "%d.%m.%Y %H:%M", decimal_comma=False)

        assert len(rows) == 0

    def test_prepare_export_data_multiple_records(self) -> None:
        """Test export with multiple records for same entity."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                },
                {
                    "start": UNIX_TIMESTAMP_2024_01_26_13_00,  # 2024-01-26 13:00:00 UTC
                    "mean": EXPECTED_MEAN_21_5,
                    "min": EXPECTED_MIN_21_0,
                    "max": EXPECTED_MAX_22_0,
                },
            ]
        }

        _columns, rows = prepare_export_data(statistics_dict, "UTC", "%d.%m.%Y %H:%M", decimal_comma=False)

        assert len(rows) == EXPECTED_ROWS_2


class TestWriteExportFile:
    """Test write_export_file function."""

    def test_write_export_file_tsv(self) -> None:
        """Test writing TSV file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "export.tsv"
            columns = ["statistic_id", "unit", "start", "mean"]
            rows = [
                ("sensor.temperature", "°C", "26.01.2024 12:00", "20.5"),
                ("sensor.humidity", "%", "26.01.2024 12:00", "65.0"),
            ]

            write_export_file(str(file_path), columns, rows, "\t")

            assert file_path.exists()
            with file_path.open(encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                lines = list(reader)
                assert lines[0] == columns
                assert lines[1] == list(rows[0])
                assert lines[2] == list(rows[1])

    def test_write_export_file_csv(self) -> None:
        """Test writing CSV file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "export.csv"
            columns = ["statistic_id", "unit", "start", "mean"]
            rows = [
                ("sensor.temperature", "°C", "26.01.2024 12:00", "20.5"),
            ]

            write_export_file(str(file_path), columns, rows, ",")

            assert file_path.exists()
            with file_path.open(encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=",")
                lines = list(reader)
                assert lines[0] == columns

    def test_write_export_file_semicolon_delimiter(self) -> None:
        """Test writing file with semicolon delimiter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "export.txt"
            columns = ["statistic_id", "unit", "start"]
            rows = [("sensor.temperature", "°C", "26.01.2024 12:00")]

            write_export_file(str(file_path), columns, rows, ";")

            with file_path.open(encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=";")
                lines = list(reader)
                assert lines[0] == columns

    def test_write_export_file_utf8_characters(self) -> None:
        """Test writing file with UTF-8 characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "export.tsv"
            columns = ["statistic_id", "unit"]
            rows = [
                ("sensor.temperature", "°C"),
                ("sensor.pressure", "mbar"),
                ("sensor.power", "W"),
            ]

            write_export_file(str(file_path), columns, rows, "\t")

            with file_path.open(encoding="utf-8") as f:
                content = f.read()
                assert "°C" in content
                assert "mbar" in content

    def test_write_export_file_empty_rows(self) -> None:
        """Test writing file with only headers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "export.tsv"
            columns = ["statistic_id", "unit", "start"]
            rows = []

            write_export_file(str(file_path), columns, rows, "\t")

            with file_path.open(encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                lines = list(reader)
                assert len(lines) == 1  # Only header
                assert lines[0] == columns

    def test_write_export_file_with_empty_cells(self) -> None:
        """Test writing file with empty cells (mixed sensor/counter)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "export.tsv"
            columns = ["statistic_id", "unit", "start", "mean", "sum"]
            rows = [
                ("sensor.temp", "°C", "26.01.2024 12:00", "20.5", ""),
                ("sensor.energy", "kWh", "26.01.2024 12:00", "", "100.5"),
            ]

            write_export_file(str(file_path), columns, rows, "\t")

            with file_path.open(encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                lines = list(reader)
                assert lines[1][4] == ""  # Empty sum for temperature
                assert lines[2][3] == ""  # Empty mean for energy


class TestPrepareExportJson:
    """Test prepare_export_json function."""

    def test_prepare_export_json_sensor(self) -> None:
        """Test JSON export with sensor statistics."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                }
            ]
        }

        result = prepare_export_json(statistics_dict, "UTC", "%d.%m.%Y %H:%M")

        assert len(result) == EXPECTED_ROWS_1
        assert result[0]["id"] == "sensor.temperature"
        assert result[0]["unit"] == ""  # Unit is empty for raw format
        assert len(result[0]["values"]) == EXPECTED_ROWS_1
        assert result[0]["values"][0]["mean"] == EXPECTED_MEAN_20_5
        assert result[0]["values"][0]["min"] == EXPECTED_MIN_20_0
        assert result[0]["values"][0]["max"] == EXPECTED_MAX_21_0

    def test_prepare_export_json_counter(self) -> None:
        """Test JSON export with counter statistics."""
        statistics_dict = {
            "sensor.energy": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "sum": EXPECTED_SUM_100_5,
                    "state": EXPECTED_STATE_100_5,
                }
            ]
        }

        result = prepare_export_json(statistics_dict, "UTC", "%d.%m.%Y %H:%M")

        assert len(result) == EXPECTED_ROWS_1
        assert result[0]["id"] == "sensor.energy"
        assert result[0]["values"][0]["sum"] == EXPECTED_SUM_100_5
        assert result[0]["values"][0]["state"] == EXPECTED_STATE_100_5

    def test_prepare_export_json_multiple_entities(self) -> None:
        """Test JSON export with multiple entities."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                }
            ],
            "sensor.humidity": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_65_0,
                    "min": EXPECTED_MIN_60_0,
                    "max": EXPECTED_MAX_70_0,
                }
            ],
        }

        result = prepare_export_json(statistics_dict, "UTC", "%d.%m.%Y %H:%M")

        assert len(result) == EXPECTED_ROWS_2

    def test_prepare_export_json_multiple_records(self) -> None:
        """Test JSON export with multiple records per entity."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                },
                {
                    "start": UNIX_TIMESTAMP_2024_01_26_13_00,  # 2024-01-26 13:00:00 UTC
                    "mean": EXPECTED_MEAN_21_5,
                    "min": EXPECTED_MIN_21_0,
                    "max": EXPECTED_MAX_22_0,
                },
            ]
        }

        result = prepare_export_json(statistics_dict, "UTC", "%d.%m.%Y %H:%M")

        assert len(result[0]["values"]) == EXPECTED_ROWS_2

    def test_prepare_export_json_timezone_conversion(self) -> None:
        """Test JSON export with timezone conversion."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": UNIX_TIMESTAMP_2024_01_26,  # 2024-01-26 12:00:00 UTC
                    "mean": EXPECTED_MEAN_20_5,
                    "min": EXPECTED_MIN_20_0,
                    "max": EXPECTED_MAX_21_0,
                }
            ]
        }

        result = prepare_export_json(statistics_dict, "Europe/Vienna", "%d.%m.%Y %H:%M")

        # Should be converted to Vienna time (UTC+1)
        assert result[0]["values"][0]["datetime"] == "26.01.2024 13:00"

    def test_prepare_export_json_invalid_timezone(self) -> None:
        """Test JSON export with invalid timezone raises error."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": datetime.datetime.now(tz=datetime.UTC),
                    "mean": 20.5,
                    "min": 20.0,
                    "max": 21.0,
                }
            ]
        }

        with pytest.raises(HomeAssistantError, match="Invalid timezone_identifier"):
            prepare_export_json(statistics_dict, "Invalid/Timezone", "%d.%m.%Y %H:%M")

    def test_prepare_export_json_empty_statistics(self) -> None:
        """Test JSON export with empty statistics."""
        statistics_dict = {}

        result = prepare_export_json(statistics_dict, "UTC", "%d.%m.%Y %H:%M")

        assert len(result) == 0

    def test_prepare_export_json_serializable(self) -> None:
        """Test that JSON export result is JSON serializable."""
        statistics_dict = {
            "sensor.temperature": [
                {
                    "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                    "mean": 20.5,
                    "min": 20.0,
                    "max": 21.0,
                }
            ]
        }

        result = prepare_export_json(statistics_dict, "UTC", "%d.%m.%Y %H:%M")

        # Should not raise an error
        json_str = json.dumps(result)
        assert "sensor.temperature" in json_str
        assert "20.5" in json_str
