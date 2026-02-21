"""Integration tests for export statistics feature."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import ServiceCall

from custom_components.import_statistics import async_setup
from custom_components.import_statistics.const import (
    ATTR_COUNTER_FIELDS,
    ATTR_DATETIME_FORMAT,
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_END_TIME,
    ATTR_ENTITIES,
    ATTR_FILENAME,
    ATTR_SPLIT_BY,
    ATTR_START_TIME,
    ATTR_TIMEZONE_IDENTIFIER,
)
from tests.conftest import get_service_handler, mock_async_add_executor_job

# Test data constants
SENSOR_TEMPERATURE_MEAN = 20.5
SENSOR_TEMPERATURE_MIN = 20.0
SENSOR_TEMPERATURE_MAX = 21.0
COUNTER_ENERGY_SUM = 10.5
COUNTER_ENERGY_STATE = 100.0
EXPECTED_RECORDS_COUNT = 2


class TestExportIntegration:
    """Integration tests for export statistics feature."""

    def normalize_file_content(self, file_path: str) -> str:
        """
        Normalize file content for comparison.

        Handles whitespace differences and format variations.
        """
        file_obj = Path(file_path)
        with file_obj.open(encoding="utf-8-sig") as f:
            content = f.read()

        if file_path.endswith(".json"):
            # For JSON files, parse and re-serialize for consistent formatting
            data = json.loads(content)
            return json.dumps(data, indent=2, sort_keys=True)
        # For CSV/TSV, strip trailing whitespace from each line and normalize line endings
        lines = content.strip().split("\n")
        return "\n".join(line.rstrip() for line in lines)

    @pytest.mark.asyncio
    async def test_export_sensor_statistics_tsv(self) -> None:
        """Test exporting sensor statistics to TSV format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                    },
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
                    },
                ],
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
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C", "sensor.humidity": "%"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_sensor_data.tsv"
            assert export_file.exists(), "Export file should be created"

            # Compare with reference file
            generated = self.normalize_file_content(str(export_file))
            reference = self.normalize_file_content("tests/testfiles/export_sensor_data.tsv")
            assert generated == reference, f"Generated file should match reference.\nGenerated:\n{generated}\n\nReference:\n{reference}"

    @pytest.mark.asyncio
    async def test_export_split_both_tsv(self) -> None:
        """Test exporting mixed statistics with split_by=both creates two files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ],
                "counter.energy_consumed": [
                    {
                        "start": 1706270400.0,
                        "sum": 10.5,
                        "state": 100.0,
                    }
                ],
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export_split.tsv",
                    ATTR_ENTITIES: ["sensor.temperature", "counter.energy_consumed"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_SPLIT_BY: "both",
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                mock_units = {"sensor.temperature": "°C", "counter.energy_consumed": "kWh"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            measurements_file = Path(tmpdir) / "export_split_measurements.tsv"
            counters_file = Path(tmpdir) / "export_split_counters.tsv"
            assert measurements_file.exists(), "Measurements split file should be created"
            assert counters_file.exists(), "Counters split file should be created"

            measurements_content = measurements_file.read_text(encoding="utf-8-sig")
            assert "mean" in measurements_content
            assert "sum" not in measurements_content

            counters_content = counters_file.read_text(encoding="utf-8-sig")
            assert "sum" in counters_content
            assert "mean" not in counters_content

    @pytest.mark.asyncio
    async def test_export_split_both_json(self) -> None:
        """Test exporting mixed statistics to JSON with split_by=both creates two JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

            mock_statistics = {
                "sensor.temperature": [
                    {
                        "start": 1706270400.0,
                        "mean": 20.5,
                        "min": 20.0,
                        "max": 21.0,
                    }
                ],
                "counter.energy_consumed": [
                    {
                        "start": 1706270400.0,
                        "sum": 10.5,
                        "state": 100.0,
                    }
                ],
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export_split.json",
                    ATTR_ENTITIES: ["sensor.temperature", "counter.energy_consumed"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_SPLIT_BY: "both",
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                mock_units = {"sensor.temperature": "°C", "counter.energy_consumed": "kWh"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            measurements_file = Path(tmpdir) / "export_split_measurements.json"
            counters_file = Path(tmpdir) / "export_split_counters.json"
            assert measurements_file.exists(), "Measurements split JSON file should be created"
            assert counters_file.exists(), "Counters split JSON file should be created"

            measurements_json = json.loads(measurements_file.read_text(encoding="utf-8-sig"))
            assert len(measurements_json) == 1
            assert measurements_json[0]["id"] == "sensor.temperature"

            counters_json = json.loads(counters_file.read_text(encoding="utf-8-sig"))
            assert len(counters_json) == 1
            assert counters_json[0]["id"] == "counter.energy_consumed"

    @pytest.mark.asyncio
    async def test_export_sensor_statistics_tsv_without_time_range(self) -> None:
        """Test exporting sensor statistics without specifying start_time/end_time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                    ATTR_FILENAME: "export_sensor_data_auto.tsv",
                    ATTR_ENTITIES: ["sensor.temperature"],
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                mock_units = {"sensor.temperature": "°C"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            export_file = Path(tmpdir) / "export_sensor_data_auto.tsv"
            assert export_file.exists(), "Export file should be created"
            assert export_file.stat().st_size > 0, "Export file should have content"

    @pytest.mark.asyncio
    async def test_export_counter_statistics_csv(self) -> None:
        """Test exporting counter statistics to CSV format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                    },
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
                    },
                ],
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
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"counter.energy_consumed": "kWh", "counter.water_used": "L"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_counter_data.csv"
            assert export_file.exists(), "Export file should be created"

            # Verify delta column is present in the output
            content = export_file.read_text()
            assert "delta" in content, "Delta column should be present in counter exports"

            # Compare with reference file
            generated = self.normalize_file_content(str(export_file))
            reference = self.normalize_file_content("tests/testfiles/export_counter_data.csv")
            assert generated == reference, f"Generated file should match reference.\nGenerated:\n{generated}\n\nReference:\n{reference}"

    @pytest.mark.asyncio
    async def test_export_counter_statistics_csv_counter_fields_sum(self) -> None:
        """Test counter_fields='sum' exports state/sum columns only for counters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

            mock_statistics = {
                "counter.energy_consumed": [
                    {"start": 1706270400.0, "sum": 10.5, "state": 100.0},
                    {"start": 1706274000.0, "sum": 11.2, "state": 110.0},
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export_counter_sum_only.csv",
                    ATTR_ENTITIES: ["counter.energy_consumed"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_DELIMITER: ",",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_COUNTER_FIELDS: "sum",
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                mock_units = {"counter.energy_consumed": "kWh"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            export_file = Path(tmpdir) / "export_counter_sum_only.csv"
            assert export_file.exists(), "Export file should be created"

            lines = export_file.read_text(encoding="utf-8-sig").strip().split("\n")
            assert lines[0] == "statistic_id,unit,start,sum,state"
            assert "delta" not in lines[0]

    @pytest.mark.asyncio
    async def test_export_counter_statistics_csv_counter_fields_delta(self) -> None:
        """Test counter_fields='delta' exports delta column only for counters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

            mock_statistics = {
                "counter.energy_consumed": [
                    {"start": 1706270400.0, "sum": 10.5, "state": 100.0},
                    {"start": 1706274000.0, "sum": 11.2, "state": 110.0},
                ]
            }

            call = ServiceCall(
                hass,
                "import_statistics",
                "export_statistics",
                {
                    ATTR_FILENAME: "export_counter_delta_only.csv",
                    ATTR_ENTITIES: ["counter.energy_consumed"],
                    ATTR_START_TIME: "2024-01-26 12:00:00",
                    ATTR_END_TIME: "2024-01-26 14:00:00",
                    ATTR_DELIMITER: ",",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_COUNTER_FIELDS: "delta",
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                mock_units = {"counter.energy_consumed": "kWh"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            export_file = Path(tmpdir) / "export_counter_delta_only.csv"
            assert export_file.exists(), "Export file should be created"

            lines = export_file.read_text(encoding="utf-8-sig").strip().split("\n")
            assert lines[0] == "statistic_id,unit,start,delta"
            assert "sum" not in lines[0]
            assert "state" not in lines[0]

            # first counter row must export delta 0
            assert lines[1].endswith(",0")

    @pytest.mark.asyncio
    async def test_export_mixed_statistics_semicolon_delimiter(self) -> None:
        """Test exporting mixed sensor/counter data with semicolon delimiter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                    },
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
                    },
                ],
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
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C", "counter.energy": "kWh"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_mixed_data.tsv"
            assert export_file.exists(), "Export file should be created"

            # Verify delta column is present in mixed exports
            content = export_file.read_text()
            assert "delta" in content, "Delta column should be present in mixed exports"

            # Compare with reference file
            generated = self.normalize_file_content(str(export_file))
            reference = self.normalize_file_content("tests/testfiles/export_mixed_data.tsv")
            assert generated == reference, f"Generated file should match reference.\nGenerated:\n{generated}\n\nReference:\n{reference}"

    @pytest.mark.asyncio
    async def test_export_sensor_to_json_format(self) -> None:
        """Test exporting sensor data to JSON format with correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file was created and is valid JSON
            export_file = Path(tmpdir) / "export_sensor_data.json"
            assert export_file.exists(), "Export file should be created"

            data = json.loads(export_file.read_text())
            assert isinstance(data, list), "JSON should be a list of records"
            assert len(data) == 1, "Should have one record"
            assert data[0]["id"] == "sensor.temperature"
            assert "values" in data[0]
            assert len(data[0]["values"]) == 1
            assert data[0]["values"][0]["mean"] == SENSOR_TEMPERATURE_MEAN
            assert data[0]["values"][0]["min"] == SENSOR_TEMPERATURE_MIN
            assert data[0]["values"][0]["max"] == SENSOR_TEMPERATURE_MAX

            # Compare with reference file
            generated = self.normalize_file_content(str(export_file))
            reference = self.normalize_file_content("tests/testfiles/export_sensor_data.json")
            assert generated == reference, f"Generated file should match reference.\nGenerated:\n{generated}\n\nReference:\n{reference}"

    @pytest.mark.asyncio
    async def test_export_counter_to_json_format(self) -> None:
        """Test exporting counter data to JSON format with correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

            mock_statistics = {
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
                    },
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
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"counter.energy": "kWh"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file was created and is valid JSON
            export_file = Path(tmpdir) / "export_counter_data.json"
            assert export_file.exists(), "Export file should be created"

            data = json.loads(export_file.read_text())
            assert isinstance(data, list), "JSON should be a list of records"
            assert len(data) == 1, "Should have one entity record"
            assert data[0]["id"] == "counter.energy"
            assert "values" in data[0]
            assert len(data[0]["values"]) == 2, "Should have two value records"
            assert data[0]["values"][0]["sum"] == COUNTER_ENERGY_SUM
            assert data[0]["values"][0]["state"] == COUNTER_ENERGY_STATE
            # First record should not have delta (no previous value)
            assert "delta" not in data[0]["values"][0]
            # Second record should have delta
            assert "delta" in data[0]["values"][1]

            # Compare with reference file
            generated = self.normalize_file_content(str(export_file))
            reference = self.normalize_file_content("tests/testfiles/export_counter_data.json")
            assert generated == reference, f"Generated file should match reference.\nGenerated:\n{generated}\n\nReference:\n{reference}"

    @pytest.mark.asyncio
    async def test_export_mixed_to_json_format(self) -> None:
        """Test exporting mixed data to JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                    },
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
                    },
                ],
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
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C", "counter.energy": "kWh"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file was created and is valid JSON
            export_file = Path(tmpdir) / "export_mixed_data.json"
            assert export_file.exists(), "Export file should be created"

            data = json.loads(export_file.read_text())
            assert isinstance(data, list), "JSON should be a list of records"
            assert len(data) == EXPECTED_RECORDS_COUNT, f"Should have {EXPECTED_RECORDS_COUNT} entity records"
            assert any(r["id"] == "sensor.temperature" for r in data)
            assert any(r["id"] == "counter.energy" for r in data)

            # Verify delta is not in sensor data but structure is preserved for counter
            sensor_record = next(r for r in data if r["id"] == "sensor.temperature")
            assert len(sensor_record["values"]) == 2, "Should have 2 sensor records"
            assert "delta" not in sensor_record["values"][0], "Sensor records should not have delta"
            assert "delta" not in sensor_record["values"][1], "Sensor records should not have delta"

            counter_record = next(r for r in data if r["id"] == "counter.energy")
            assert len(counter_record["values"]) == 2, "Should have 2 counter records"
            assert "delta" not in counter_record["values"][0], "First counter record should not have delta"
            assert "delta" in counter_record["values"][1], "Second counter record should have delta"

            # Compare with reference file
            generated = self.normalize_file_content(str(export_file))
            reference = self.normalize_file_content("tests/testfiles/export_mixed_data.json")
            assert generated == reference, f"Generated file should match reference.\nGenerated:\n{generated}\n\nReference:\n{reference}"

    @pytest.mark.asyncio
    async def test_export_with_decimal_comma_format(self) -> None:
        """Test export with comma as decimal separator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                    ATTR_DECIMAL: "comma (',')",  # Use comma as decimal separator
                    ATTR_DELIMITER: ",",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_decimal_comma.csv"
            assert export_file.exists(), "Export file should be created"

            # Check content has comma as decimal separator
            content = export_file.read_text()
            assert "20,5" in content, "Values should use comma as decimal separator"

    @pytest.mark.asyncio
    async def test_export_with_custom_datetime_format(self) -> None:
        """Test export with custom datetime format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_iso_format.tsv"
            assert export_file.exists(), "Export file should be created"

            # Check content has ISO format datetime
            content = export_file.read_text()
            assert "2024-01-26 12:00" in content, "Should use ISO datetime format"

    @pytest.mark.asyncio
    async def test_export_with_timezone_conversion(self) -> None:
        """Test export with timezone conversion (UTC to Europe/Vienna)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file was created
            export_file = Path(tmpdir) / "export_vienna_tz.tsv"
            assert export_file.exists(), "Export file should be created"

            # Check content shows Vienna time (13:00)
            content = export_file.read_text()
            assert "13:00" in content, "Should show time in Vienna timezone"

    @pytest.mark.asyncio
    async def test_export_file_existence_check(self) -> None:
        """Test that exported files are created with content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = MagicMock()
            hass.config = MagicMock()
            hass.config.config_dir = tmpdir

            hass.async_add_executor_job = mock_async_add_executor_job

            await async_setup(hass, {})
            service_handler = get_service_handler(hass, "export_statistics")

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
                },
            )

            with patch("custom_components.import_statistics.export_service.get_statistics_from_recorder") as mock_get_stats:
                # Return tuple: (statistics_dict, units_dict)
                mock_units = {"sensor.temperature": "°C"}
                mock_get_stats.return_value = (mock_statistics, mock_units)
                await service_handler(call)

            # Verify file exists and has content
            export_file = Path(tmpdir) / "test_export.tsv"
            assert export_file.exists(), "Export file should be created"
            assert export_file.stat().st_size > 0, "Export file should have content"
            assert "sensor.temperature" in export_file.read_text(), "File should contain entity data"
