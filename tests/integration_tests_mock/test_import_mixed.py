"""Integration tests for mixed import (sensor + counter data in one file)."""

import datetime as dt
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.core import ServiceCall

from custom_components.import_statistics import async_setup
from custom_components.import_statistics.const import (
    ATTR_DECIMAL,
    ATTR_DELIMITER,
    ATTR_FILENAME,
    ATTR_TIMEZONE_IDENTIFIER,
)
from tests.conftest import create_mock_recorder_instance, get_service_handler, mock_async_add_executor_job


def _create_mixed_hass(tmpdir: str) -> MagicMock:
    """Create a mock hass object configured for mixed import tests."""
    hass = MagicMock()
    hass.config = MagicMock()
    hass.config.config_dir = tmpdir
    hass.config.time_zone = "UTC"
    hass.async_add_executor_job = mock_async_add_executor_job
    hass.states = MagicMock()
    hass.states.set = MagicMock()

    def mock_get_state(entity_id: str) -> MagicMock:
        mock_state = MagicMock()
        unit_map = {
            "sensor.mixed_temp": "°C",
            "sensor.mixed_humidity": "%",
            "sensor.mixed_energy": "kWh",
            "sensor.mixed_water": "L",
        }
        mock_state.attributes = {"unit_of_measurement": unit_map.get(entity_id, "unknown")}
        return mock_state

    hass.states.get = mock_get_state
    return hass


def _collect_calls_by_id(mock_obj: MagicMock) -> dict:
    """Collect mock import calls into a dict keyed by statistic_id."""
    calls_by_id = {}
    for call_obj in mock_obj.call_args_list:
        metadata = call_obj[0][1]
        statistics = call_obj[0][2]
        calls_by_id[metadata["statistic_id"]] = (metadata, statistics)
    return calls_by_id


def _assert_sensor_metadata(meta: dict, *, unit: str, source: str = "recorder") -> None:
    """Assert metadata matches sensor (min/max/mean) type."""
    assert meta["mean_type"] == StatisticMeanType.ARITHMETIC
    assert meta["has_sum"] is False
    assert meta["unit_of_measurement"] == unit
    assert meta["source"] == source


def _assert_counter_metadata(meta: dict, *, unit: str, source: str = "recorder") -> None:
    """Assert metadata matches counter (sum/state) type."""
    assert meta["mean_type"] == StatisticMeanType.NONE
    assert meta["has_sum"] is True
    assert meta["unit_of_measurement"] == unit
    assert meta["source"] == source


def _assert_sensor_stats(stats: list, expected: list[tuple[float, float, float]]) -> None:
    """Assert sensor statistics match expected (min, max, mean) tuples."""
    assert len(stats) == len(expected)
    for stat, (exp_min, exp_max, exp_mean) in zip(stats, expected, strict=True):
        assert pytest.approx(stat["min"]) == pytest.approx(exp_min)
        assert pytest.approx(stat["max"]) == pytest.approx(exp_max)
        assert pytest.approx(stat["mean"]) == pytest.approx(exp_mean)


def _assert_counter_stats(stats: list, expected: list[tuple[float, float]]) -> None:
    """Assert counter statistics match expected (sum, state) tuples."""
    assert len(stats) == len(expected)
    for stat, (exp_sum, exp_state) in zip(stats, expected, strict=True):
        assert pytest.approx(stat["sum"]) == pytest.approx(exp_sum)
        assert pytest.approx(stat["state"]) == pytest.approx(exp_state)


class TestMixedImportIntegration:
    """Integration tests for mixed sensor + counter import functionality."""

    @pytest.mark.asyncio
    async def test_import_mixed_csv_file(self) -> None:
        """Test importing a TSV file with both sensor (min/max/mean) and counter (sum/state) data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mixed_hass(tmpdir)

            await async_setup(hass, {})
            import_handler = get_service_handler(hass, "import_from_file")

            # Create mixed TSV file with sensor and counter data
            test_file = Path(tmpdir) / "mixed_data.tsv"
            test_file.write_text(
                "statistic_id\tunit\tstart\tmin\tmax\tmean\tsum\tstate\n"
                "sensor.mixed_temp\t°C\t26.01.2024 12:00\t18.5\t22.3\t20.1\t\t\n"
                "sensor.mixed_temp\t°C\t26.01.2024 13:00\t19.0\t23.0\t21.0\t\t\n"
                "sensor.mixed_humidity\t%\t26.01.2024 12:00\t45\t55\t50\t\t\n"
                "sensor.mixed_humidity\t%\t26.01.2024 13:00\t48\t58\t53\t\t\n"
                "sensor.mixed_energy\tkWh\t26.01.2024 12:00\t\t\t\t10.5\t100\n"
                "sensor.mixed_energy\tkWh\t26.01.2024 13:00\t\t\t\t11.2\t110\n"
                "sensor.mixed_water\tL\t26.01.2024 12:00\t\t\t\t500\t1000\n"
                "sensor.mixed_water\tL\t26.01.2024 13:00\t\t\t\t520\t1020\n",
                encoding="utf-8",
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "mixed_data.tsv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            ):
                await import_handler(call)

                assert mock_import.call_count == 4, f"Expected 4 calls, got {mock_import.call_count}"
                calls_by_id = _collect_calls_by_id(mock_import)

                # Verify sensor entities (min/max/mean)
                _assert_sensor_metadata(calls_by_id["sensor.mixed_temp"][0], unit="°C")
                _assert_sensor_stats(calls_by_id["sensor.mixed_temp"][1], [(18.5, 22.3, 20.1), (19.0, 23.0, 21.0)])

                _assert_sensor_metadata(calls_by_id["sensor.mixed_humidity"][0], unit="%")
                _assert_sensor_stats(calls_by_id["sensor.mixed_humidity"][1], [(45.0, 55.0, 50.0), (48.0, 58.0, 53.0)])

                # Verify counter entities (sum/state)
                _assert_counter_metadata(calls_by_id["sensor.mixed_energy"][0], unit="kWh")
                _assert_counter_stats(calls_by_id["sensor.mixed_energy"][1], [(10.5, 100.0), (11.2, 110.0)])

                _assert_counter_metadata(calls_by_id["sensor.mixed_water"][0], unit="L")
                _assert_counter_stats(calls_by_id["sensor.mixed_water"][1], [(500.0, 1000.0), (520.0, 1020.0)])

                # Verify timestamps are datetime objects with UTC timezone
                for _meta, stats in calls_by_id.values():
                    for stat in stats:
                        assert isinstance(stat["start"], dt.datetime)
                        assert stat["start"].tzinfo is not None

    @pytest.mark.asyncio
    async def test_import_mixed_json(self) -> None:
        """Test importing mixed sensor + counter data from JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mixed_hass(tmpdir)

            await async_setup(hass, {})
            json_handler = get_service_handler(hass, "import_from_json")

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_json",
                {
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DECIMAL: "dot ('.')",
                    "entities": [
                        {
                            "id": "sensor.mixed_temp",
                            "unit": "°C",
                            "values": [
                                {"datetime": "26.01.2024 12:00", "min": 18.5, "max": 22.3, "mean": 20.1},
                                {"datetime": "26.01.2024 13:00", "min": 19.0, "max": 23.0, "mean": 21.0},
                            ],
                        },
                        {
                            "id": "sensor.mixed_humidity",
                            "unit": "%",
                            "values": [
                                {"datetime": "26.01.2024 12:00", "min": 45, "max": 55, "mean": 50},
                                {"datetime": "26.01.2024 13:00", "min": 48, "max": 58, "mean": 53},
                            ],
                        },
                        {
                            "id": "sensor.mixed_energy",
                            "unit": "kWh",
                            "values": [
                                {"datetime": "26.01.2024 12:00", "sum": 10.5, "state": 100},
                                {"datetime": "26.01.2024 13:00", "sum": 11.2, "state": 110},
                            ],
                        },
                        {
                            "id": "sensor.mixed_water",
                            "unit": "L",
                            "values": [
                                {"datetime": "26.01.2024 12:00", "sum": 500, "state": 1000},
                                {"datetime": "26.01.2024 13:00", "sum": 520, "state": 1020},
                            ],
                        },
                    ],
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_import_statistics") as mock_import,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            ):
                await json_handler(call)

                assert mock_import.call_count == 4, f"Expected 4 calls, got {mock_import.call_count}"
                calls_by_id = _collect_calls_by_id(mock_import)

                # Verify sensor entities (min/max/mean)
                _assert_sensor_metadata(calls_by_id["sensor.mixed_temp"][0], unit="°C")
                _assert_sensor_stats(calls_by_id["sensor.mixed_temp"][1], [(18.5, 22.3, 20.1), (19.0, 23.0, 21.0)])

                _assert_sensor_metadata(calls_by_id["sensor.mixed_humidity"][0], unit="%")
                _assert_sensor_stats(calls_by_id["sensor.mixed_humidity"][1], [(45.0, 55.0, 50.0), (48.0, 58.0, 53.0)])

                # Verify counter entities (sum/state)
                _assert_counter_metadata(calls_by_id["sensor.mixed_energy"][0], unit="kWh")
                _assert_counter_stats(calls_by_id["sensor.mixed_energy"][1], [(10.5, 100.0), (11.2, 110.0)])

                _assert_counter_metadata(calls_by_id["sensor.mixed_water"][0], unit="L")
                _assert_counter_stats(calls_by_id["sensor.mixed_water"][1], [(500.0, 1000.0), (520.0, 1020.0)])

    @pytest.mark.asyncio
    async def test_import_mixed_csv_with_external_entities(self) -> None:
        """Test importing mixed data with external entities (colon separator)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hass = _create_mixed_hass(tmpdir)
            hass.states.get = MagicMock(return_value=None)  # No entity needed for external

            await async_setup(hass, {})
            import_handler = get_service_handler(hass, "import_from_file")

            # Create mixed TSV file with external entities (colon separator)
            test_file = Path(tmpdir) / "mixed_external.tsv"
            test_file.write_text(
                "statistic_id\tunit\tstart\tmin\tmax\tmean\tsum\tstate\n"
                "sensor:mixed_ext_temp\t°C\t26.01.2024 12:00\t18.5\t22.3\t20.1\t\t\n"
                "sensor:mixed_ext_temp\t°C\t26.01.2024 13:00\t19.0\t23.0\t21.0\t\t\n"
                "sensor:mixed_ext_energy\tkWh\t26.01.2024 12:00\t\t\t\t10.5\t100\n"
                "sensor:mixed_ext_energy\tkWh\t26.01.2024 13:00\t\t\t\t11.2\t110\n",
                encoding="utf-8",
            )

            call = ServiceCall(
                hass,
                "import_statistics",
                "import_from_file",
                {
                    ATTR_FILENAME: "mixed_external.tsv",
                    ATTR_TIMEZONE_IDENTIFIER: "UTC",
                    ATTR_DELIMITER: "\t",
                    ATTR_DECIMAL: "dot ('.')",
                },
            )

            with (
                patch("custom_components.import_statistics.import_service.async_add_external_statistics") as mock_external,
                patch("custom_components.import_statistics.import_service.get_instance", return_value=create_mock_recorder_instance()),
            ):
                await import_handler(call)

                assert mock_external.call_count == 2, f"Expected 2 calls, got {mock_external.call_count}"
                calls_by_id = _collect_calls_by_id(mock_external)

                # Verify external sensor entity (min/max/mean)
                _assert_sensor_metadata(calls_by_id["sensor:mixed_ext_temp"][0], unit="°C", source="sensor")
                _assert_sensor_stats(calls_by_id["sensor:mixed_ext_temp"][1], [(18.5, 22.3, 20.1), (19.0, 23.0, 21.0)])

                # Verify external counter entity (sum/state)
                _assert_counter_metadata(calls_by_id["sensor:mixed_ext_energy"][0], unit="kWh", source="sensor")
                _assert_counter_stats(calls_by_id["sensor:mixed_ext_energy"][1], [(10.5, 100.0), (11.2, 110.0)])
