"""Test convert_delta_dataframe_with_references function."""

import datetime as dt
import zoneinfo

import pandas as pd
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.import_statistics.helpers import UnitFrom
from custom_components.import_statistics.prepare_data import convert_delta_dataframe_with_references


def test_convert_delta_dataframe_with_references_single_statistic() -> None:
    """Test convert_delta_dataframe_with_references with single statistic."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature", "sensor.temperature"],
            "start": ["01.01.2022 00:00", "01.01.2022 01:00"],
            "delta": ["10.5", "5.2"],
            "unit": ["°C", "°C"],
        }
    )

    references = {"sensor.temperature": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0}}

    result = convert_delta_dataframe_with_references(df, references, tz_id, datetime_format, UnitFrom.TABLE)

    assert len(result) == 1
    assert "sensor.temperature" in result
    metadata, stats = result["sensor.temperature"]
    assert metadata["has_sum"] is True
    assert metadata["mean_type"].value == 0  # NONE
    assert len(stats) == 2
    assert stats[0]["sum"] == 110.5
    assert stats[1]["sum"] == 115.7


def test_convert_delta_dataframe_with_references_multiple_statistics() -> None:
    """Test convert_delta_dataframe_with_references with multiple statistics."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.energy", "sensor.energy", "sensor.gas", "sensor.gas"],
            "start": ["01.01.2022 00:00", "01.01.2022 01:00", "01.01.2022 00:00", "01.01.2022 01:00"],
            "delta": [10.5, 5.2, 1.5, 2.1],
            "unit": ["kWh", "kWh", "m³", "m³"],
        }
    )

    references = {
        "sensor.energy": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0},
        "sensor.gas": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 50.0, "state": 50.0},
    }

    result = convert_delta_dataframe_with_references(df, references, tz_id, datetime_format, UnitFrom.TABLE)

    assert len(result) == 2
    assert "sensor.energy" in result
    assert "sensor.gas" in result

    # Check energy
    energy_meta, energy_stats = result["sensor.energy"]
    assert len(energy_stats) == 2
    assert energy_stats[0]["sum"] == 110.5

    # Check gas
    gas_meta, gas_stats = result["sensor.gas"]
    assert len(gas_stats) == 2
    assert gas_stats[0]["sum"] == 51.5


def test_convert_delta_dataframe_with_references_missing_reference() -> None:
    """Test convert_delta_dataframe_with_references raises error for missing reference."""
    tz_id = "Europe/Vienna"
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature"],
            "start": ["01.01.2022 00:00"],
            "delta": [10.5],
            "unit": ["°C"],
        }
    )

    references = {"sensor.temperature": None}

    with pytest.raises(HomeAssistantError, match="Failed to find database reference"):
        convert_delta_dataframe_with_references(df, references, tz_id, datetime_format, UnitFrom.TABLE)


def test_convert_delta_dataframe_with_references_unit_from_entity() -> None:
    """Test convert_delta_dataframe_with_references with unit_from_entity."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature"],
            "start": ["01.01.2022 00:00"],
            "delta": [10.5],
        }
    )

    references = {"sensor.temperature": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0}}

    result = convert_delta_dataframe_with_references(df, references, tz_id, datetime_format, UnitFrom.ENTITY)

    assert len(result) == 1
    metadata, stats = result["sensor.temperature"]
    assert metadata["unit_of_measurement"] == ""  # Empty for unit_from_entity


def test_convert_delta_dataframe_with_references_external_statistics() -> None:
    """Test convert_delta_dataframe_with_references with external (colon-format) statistic."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["custom:energy", "custom:energy"],
            "start": ["01.01.2022 00:00", "01.01.2022 01:00"],
            "delta": ["10.5", "5.2"],
            "unit": ["kWh", "kWh"],
        }
    )

    references = {"custom:energy": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0}}

    result = convert_delta_dataframe_with_references(df, references, tz_id, datetime_format, UnitFrom.TABLE)

    assert len(result) == 1
    metadata, stats = result["custom:energy"]
    assert metadata["source"] == "custom"
    assert metadata["has_sum"] is True


def test_convert_delta_dataframe_with_references_no_delta_column() -> None:
    """Test convert_delta_dataframe_with_references raises error if delta column missing."""
    tz_id = "Europe/Vienna"
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature"],
            "start": ["01.01.2022 00:00"],
            "sum": [100.0],
            "unit": ["°C"],
        }
    )

    references = {}

    with pytest.raises(HomeAssistantError, match="Delta column not found"):
        convert_delta_dataframe_with_references(df, references, tz_id, datetime_format, UnitFrom.TABLE)


def test_convert_delta_dataframe_with_references_invalid_rows_filtered() -> None:
    """Test convert_delta_dataframe_with_references silently filters invalid rows."""
    tz_id = "Europe/Vienna"
    tz = zoneinfo.ZoneInfo(tz_id)
    datetime_format = "%d.%m.%Y %H:%M"

    df = pd.DataFrame(
        {
            "statistic_id": ["sensor.temperature", "sensor.temperature"],
            "start": ["01.01.2022 00:30", "01.01.2022 01:00"],  # First row has invalid timestamp (not full hour)
            "delta": [10.5, 5.2],
            "unit": ["°C", "°C"],
        }
    )

    references = {"sensor.temperature": {"start": dt.datetime(2021, 12, 31, 23, 0, tzinfo=tz), "sum": 100.0, "state": 100.0}}

    result = convert_delta_dataframe_with_references(df, references, tz_id, datetime_format, UnitFrom.TABLE)

    # Only valid row should be included
    metadata, stats = result["sensor.temperature"]
    assert len(stats) == 1
    assert stats[0]["sum"] == 105.2
