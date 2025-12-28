"""Integration tests for export statistics feature."""

import datetime
import json
import tempfile
import zoneinfo
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import ServiceCall

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
)


class TestExportIntegration:
    """Integration tests for export statistics feature."""

    def normalize_file_content(self, file_path: str) -> str:
        """
        Normalize file content for comparison.

        Handles whitespace differences and format variations.
        """
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        if file_path.endswith(".json"):
            # For JSON files, parse and re-serialize for consistent formatting
            data = json.loads(content)
            return json.dumps(data, indent=2, sort_keys=True)
        # For CSV/TSV, strip trailing whitespace from each line and normalize line endings
        lines = content.strip().split('\n')
        return '\n'.join(line.rstrip() for line in lines)

    def test_export_sensor_statistics_tsv(self) -> None:
        """Test exporting sensor statistics to TSV format."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            # Create mock statistics data in raw format (from recorder API)
            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    },
                    {
                        "start": 1706274000.0,  # 2024-01-26 13:00:00 UTC
                        "mean": 20.1,
                        "min": 19.8,
                        "max": 20.5,
                    }
                ],
                "sensor.humidity": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                        "mean": 50.0,
                        "min": 45.0,
                        "max": 55.0,
                    },
                    {
                        "start": 1706274000.0,  # 2024-01-26 13:00:00 UTC
                        "mean": 51.0,
                        "min": 46.0,
                        "max": 56.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export_sensor_data.tsv",
                    ATTR_ENTITIES: ["sensor.temperature", "sensor.humidity"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_sensor_data.tsv"
            assert export_file.exists(), "Export file should be created"

            # Compare with reference file
            generated = self.normalize_file_content(str(export_file))
            reference = self.normalize_file_content("tests/testfiles/export_sensor_data.tsv")
            assert generated == reference, f"Generated file should match reference.\nGenerated:\n{generated}\n\nReference:\n{reference}"

    def test_export_counter_statistics_csv(self) -> None:
        """Test exporting counter statistics to CSV format."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            # Create mock counter statistics data
            mock_statistics = {
                "counter.energy_consumed": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                        "sum": 10.5,
                        "state": 100.0,
                    },
                    {
                        "start": 1706274000.0,  # 2024-01-26 13:00:00 UTC
                        "sum": 11.2,
                        "state": 110.0,
                    }
                ],
                "counter.water_used": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                        "sum": 5.3,
                        "state": 50.0,
                    },
                    {
                        "start": 1706274000.0,  # 2024-01-26 13:00:00 UTC
                        "sum": 5.8,
                        "state": 55.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export_counter_data.csv",
                    ATTR_ENTITIES: ["counter.energy_consumed", "counter.water_used"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_DELIMITER: ",",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_counter_data.csv"
            assert export_file.exists(), "Export file should be created"

            # Compare with reference file
            generated = self.normalize_file_content(str(export_file))
            reference = self.normalize_file_content("tests/testfiles/export_counter_data.csv")
            assert generated == reference, f"Generated file should match reference.\nGenerated:\n{generated}\n\nReference:\n{reference}"

    def test_export_mixed_statistics_semicolon_delimiter(self) -> None:
        """Test exporting mixed sensor/counter data with semicolon delimiter."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            # Create mock mixed statistics data
            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    },
                    {
                        "start": 1706274000.0,  # 2024-01-26 13:00:00 UTC
                        "mean": 20.1,
                        "min": 19.8,
                        "max": 20.5,
                    }
                ],
                "counter.energy": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                        "sum": 10.5,
                        "state": 100.0,
                    },
                    {
                        "start": 1706274000.0,  # 2024-01-26 13:00:00 UTC
                        "sum": 11.2,
                        "state": 110.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export_mixed_data.tsv",
                    ATTR_ENTITIES: ["sensor.temperature", "counter.energy"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_DELIMITER: ";",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_mixed_data.tsv"
            assert export_file.exists(), "Export file should be created"

            # Compare with reference file
            generated = self.normalize_file_content(str(export_file))
            reference = self.normalize_file_content("tests/testfiles/export_mixed_data.tsv")
            assert generated == reference, f"Generated file should match reference.\nGenerated:\n{generated}\n\nReference:\n{reference}"

    def test_export_sensor_to_json_format(self) -> None:
        """Test exporting sensor data to JSON format with correct structure."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
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
                    ATTR_FILENAME: "export_sensor_data.json",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file was created and is valid JSON
            export_file = Path(tmpdir) / "export_sensor_data.json"
            assert export_file.exists(), "Export file should be created"

            data = json.loads(export_file.read_text())
            assert isinstance(data, list), "JSON should be a list of records"
            assert len(data) == 1, "Should have one record"
            assert data[0]["id"] == "sensor.temperature"
            assert "values" in data[0]
            assert len(data[0]["values"]) == 1
            assert data[0]["values"][0]["mean"] == 20.5
            assert data[0]["values"][0]["min"] == 20.0
            assert data[0]["values"][0]["max"] == 21.0

    def test_export_counter_to_json_format(self) -> None:
        """Test exporting counter data to JSON format with correct structure."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "counter.energy": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                        "sum": 10.5,
                        "state": 100.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export_counter_data.json",
                    ATTR_ENTITIES: ["counter.energy"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file was created and is valid JSON
            export_file = Path(tmpdir) / "export_counter_data.json"
            assert export_file.exists(), "Export file should be created"

            data = json.loads(export_file.read_text())
            assert isinstance(data, list), "JSON should be a list of records"
            assert len(data) == 1, "Should have one record"
            assert data[0]["id"] == "counter.energy"
            assert "values" in data[0]
            assert len(data[0]["values"]) == 1
            assert data[0]["values"][0]["sum"] == 10.5
            assert data[0]["values"][0]["state"] == 100.0

    def test_export_mixed_to_json_format(self) -> None:
        """Test exporting mixed data to JSON format."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ],
                "counter.energy": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
                        "sum": 10.5,
                        "state": 100.0,
                    }
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export_mixed_data.json",
                    ATTR_ENTITIES: ["sensor.temperature", "counter.energy"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file was created and is valid JSON
            export_file = Path(tmpdir) / "export_mixed_data.json"
            assert export_file.exists(), "Export file should be created"

            data = json.loads(export_file.read_text())
            assert isinstance(data, list), "JSON should be a list of records"
            assert len(data) == 2, "Should have two records"
            assert any(r["id"] == "sensor.temperature" for r in data)
            assert any(r["id"] == "counter.energy" for r in data)

    def test_export_with_decimal_comma_format(self) -> None:
        """Test export with comma as decimal separator."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
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
                    ATTR_FILENAME: "export_decimal_comma.csv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_DECIMAL: True,  # Use comma as decimal separator
                    ATTR_DELIMITER: ",",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_decimal_comma.csv"
            assert export_file.exists(), "Export file should be created"

            # Check content has comma as decimal separator
            content = export_file.read_text()
            assert "20,5" in content, "Values should use comma as decimal separator"

    def test_export_with_custom_datetime_format(self) -> None:
        """Test export with custom datetime format."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC
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
                    ATTR_FILENAME: "export_iso_format.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_DATETIME_FORMAT: "%Y-%m-%d %H:%M",  # ISO format
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_iso_format.tsv"
            assert export_file.exists(), "Export file should be created"

            # Check content has ISO format datetime
            content = export_file.read_text()
            assert "2024-01-26 12:00" in content, "Should use ISO datetime format"

    def test_export_with_timezone_conversion(self) -> None:
        """Test export with timezone conversion (UTC to Europe/Vienna)."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            # UTC data
            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,  # 2024-01-26 12:00:00 UTC = 13:00:00 Vienna (UTC+1)
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
                    ATTR_FILENAME: "export_vienna_tz.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 13:00:00",  # 13:00 in Vienna timezone
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "Europe/Vienna",
                    ATTR_DATETIME_FORMAT: "%d.%m.%Y %H:%M",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_vienna_tz.tsv"
            assert export_file.exists(), "Export file should be created"

            # Check content shows Vienna time (13:00)
            content = export_file.read_text()
            assert "13:00" in content, "Should show time in Vienna timezone"

    def test_export_file_existence_check(self) -> None:
        """Test that exported files are created with content."""
        from custom_components.import_statistics import setup

        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            setup(hass, {})
            service_handler = hass.services.register.call_args_list[-1][0][2]

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,
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
                    ATTR_FILENAME: "test_export.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                }
            )

            with patch("custom_components.import_statistics.get_statistics_from_recorder") as mock_get_stats:
                mock_get_stats.return_value = mock_statistics
                service_handler(call)

            # Verify file exists and has content
            export_file = Path(tmpdir) / "test_export.tsv"
            assert export_file.exists(), "Export file should be created"
            assert export_file.stat().st_size > 0, "Export file should have content"
            assert "sensor.temperature" in export_file.read_text(), "File should contain entity data"
